"""Fail-closed delivery and PDF checks; visual review is a separate gate."""
import hashlib
from pathlib import Path

def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def delivery_files(directory):
    files=sorted(Path(directory).iterdir())
    if len(files)!=2 or {x.suffix.lower() for x in files}!={'.dwg','.pdf'} or any(not x.is_file() or x.stat().st_size==0 for x in files):raise ValueError('Expected exactly two nonempty DWG/PDF deliverables')
    return [x.name for x in files]

def final_status(native_ok, output_ok, visual_ok, coverage_ok=True):
    if not(native_ok and output_ok and coverage_ok):return 'FAILED'
    return 'DRAFT_VERIFIED' if visual_ok else 'REVIEW_REQUIRED'

def check_upstream(report,require_export=False):
    if report.get('status') in ('FAILED','UNKNOWN') or report.get('native_worker_exit_code')!=0:raise ValueError('Upstream failed/unknown stage cannot be promoted')
    if require_export and report.get('export',{}).get('viewer_exit_code')!=0:raise ValueError('DWG viewer did not exit successfully')

def check_visual_review(review,dwg,pdf):
    if review.get('dwg_sha256')!=sha256(dwg) or review.get('pdf_sha256')!=sha256(pdf):raise ValueError('Visual review file identity changed')
    if any(review.get('checks',{}).get(k) is not True for k in ('template','views','dimensions','symbols','tables','legibility','projection')):raise ValueError('Incomplete visual review')
    return True

def check_native_plan(snapshot,plan,facts,bindings=None):
    views=[v for v in snapshot if v.get('source')]
    planned=plan.get('views',[])+plan.get('sections',[])
    if len(views)!=len(planned):raise ValueError('Native view count differs from plan')
    by_view={v['view']:v for v in views}
    layout=[];sheet=plan.get('sheet',{})
    for expected in planned:
        actual=by_view.get(expected['id'])
        if not actual or Path(actual['source'])!=Path(facts['path']) or actual['configuration']!=facts['configuration']:raise ValueError('Native view/source/configuration mismatch')
        if abs(actual['scale']-expected['scale'])>1e-8:raise ValueError('Native view scale mismatch')
        if 'model_view' in expected and actual.get('orientation')!=expected['model_view']:raise ValueError('Native view orientation mismatch')
        if len(actual.get('position',[]))<2 or max(abs(a*1000-b) for a,b in zip(actual['position'][:2],expected['position_mm']))>.5:raise ValueError('Native view position mismatch')
        box=[x*1000 for x in actual['outline']]
        if box[0]<0 or box[1]<0 or box[2]>sheet['width_mm'] or box[3]>sheet['height_mm']:layout.append('Out-of-sheet view: '+expected['id'])
    from planner import overlaps
    for i,a in enumerate(views):
        for b in views[i+1:]:
            if overlaps(a['outline'],b['outline']):layout.append('View overlap: '+a['view']+' / '+b['view'])
    items=[a for v in snapshot for a in v.get('annotations',[])]
    values=[a['value_si'] for a in items if 'value_si' in a]
    definitions=[x['expected_mm']/1000 for key in ('dimensions','diameters','radial') for x in plan.get(key,[])]
    definitions += [x['expected_deg']*3.141592653589793/180 if x['direction']=='angular' else x['expected_mm']/1000 for x in plan.get('linear',[])]
    for value in definitions:
        match=next((i for i,x in enumerate(values) if abs(x-value)<1e-7),None)
        if match is None:raise ValueError('Native dimension definition missing or changed')
        values.pop(match)
    dimension_ops=[x for k in ('dimensions','diameters','radial','linear') for x in plan.get(k,[])]
    for item in dimension_ops:
        if 'id' not in item:continue  # helper-only probes; full plan validation requires IDs
        binding=(bindings or {}).get(item['id'])
        if not binding or binding['view']!=item['view']:raise ValueError('Missing native dimension identity')
        candidates=[a for a in by_view[item['view']]['annotations'] if a.get('annotation_name')==binding['annotation_name']]
        value=item['expected_deg']*3.141592653589793/180 if item.get('direction')=='angular' else item['expected_mm']/1000
        if len(candidates)!=1 or abs(candidates[0].get('value_si',float('inf'))-value)>1e-7:raise ValueError('Native dimension identity/view/value mismatch')
        position=binding['position'][:2] if plan.get('auto_arrange') else [x/1000 for x in item['position_mm']]
        if max(abs(a-b)*1000 for a,b in zip(candidates[0]['position'][:2],position))>.5:raise ValueError('Native dimension position mismatch')
    for name in plan.get('model_dimensions',{}).get('keep',[]):
        binding=(bindings or {}).get('model:'+name)
        source_dims=[d for f in facts['features'] for d in f['dimensions'] if d['name']==name or d['name'].startswith(name+'@')]
        actual=[a for v in views if binding and v['view']==binding['view'] for a in v['annotations'] if a.get('annotation_name')==binding['annotation_name'] and a.get('name')==name]
        if not source_dims or len(actual)!=1 or abs(actual[0]['value_si']-source_dims[0]['value_si'])>1e-7:raise ValueError('Selected model dimension missing/changed')
    for ident in plan.get('dimension_ids',[]):
        binding=(bindings or {}).get(ident)
        if not binding:raise ValueError('Missing native annotation identity: '+ident)
        candidates=[a for v in snapshot if (v['view']==binding['view'] if binding['view'] else not v.get('source')) for a in v['annotations'] if a.get('annotation_name')==binding['annotation_name']]
        if len(candidates)!=1 or max(abs(a-b)*1000 for a,b in zip(candidates[0]['position'][:2],binding['position'][:2]))>.5:raise ValueError('Native annotation identity/position changed')
        x,y=candidates[0]['position'][:2]
        if x<0 or y<0 or x*1000>sheet['width_mm'] or y*1000>sheet['height_mm']:raise ValueError('Native annotation outside sheet')
    texts=[a.get('text','') for a in items]
    for text in [x['text'] for key in ('notes','labels') for x in plan.get(key,[])]:
        if text not in texts:raise ValueError('Native note/label missing')
    tables=[a['rows'] for a in items if 'rows' in a]
    for table in plan.get('tables',[]):
        if table['rows'] not in tables:raise ValueError('Native table changed')
    return {'status':'PASS','planned_dimensions_checked':len(definitions),'views_checked':len(views),'layout_flags':layout}


def check_readback(native, readback, position_tolerance_mm=0.5):
    """Compare dimension definitions and their paper XY positions across formats.

    A drawing dimension's Z coordinate is view depth and is not a paper position.
    Match globally: DWG imports flatten native drawing views into one sketch.
    """
    original=[a for v in native for a in v.get('annotations',[]) if 'value_si' in a]
    imported=[a for v in readback for a in v.get('annotations',[]) if 'value_si' in a]
    if not original or len(original)!=len(imported):raise ValueError('Readback dimension count changed or empty')
    remaining=list(imported)
    for a in original:
        candidates=[b for b in remaining if abs(a['value_si']-b['value_si'])<1e-7]
        if not candidates:raise ValueError('Readback dimension value/scale changed')
        distance=lambda b: max(abs(x-y)*1000 for x,y in zip(a['position'][:2],b['position'][:2]))
        match=min(candidates,key=distance)
        if distance(match)>position_tolerance_mm:raise ValueError('Readback dimension position changed')
        remaining.remove(match)
    return {'status':'PASS','dimensions_checked':len(original),'position_tolerance_mm':position_tolerance_mm}

def check_pdf(path, sheet_mm, expected_texts):
    from pypdf import PdfReader
    reader=PdfReader(path)
    if len(reader.pages)!=1:raise ValueError('PDF must contain one page')
    page=reader.pages[0]; actual=[float(page.mediabox.width)*25.4/72,float(page.mediabox.height)*25.4/72]
    if any(abs(a-b)>0.6 for a,b in zip(actual,sheet_mm)):raise ValueError('PDF paper size changed')
    text=page.extract_text() or ''
    compact=lambda x: ''.join(x.split()).replace('⌀','Ø').replace('∅','Ø')
    missing=[x for x in expected_texts if compact(x) not in compact(text)]
    return {'status':'PASS' if not missing else 'PARTIAL_OR_OUTLINED_TEXT_REQUIRES_VISUAL_REVIEW','page_count':1,'paper_mm':actual,'sha256':sha256(path),'expected_texts_checked':len(expected_texts)-len(missing),'unresolved_texts':missing,'expected_texts':expected_texts,'visual_review':'NOT_CHECKED'}

def verify_native(plan,report):
    import json
    from validate_plan import validate,check_coverage
    check_upstream(report)
    validate(plan,allow_existing=True)
    facts=json.loads(Path(plan['facts']).read_text(encoding='utf-8-sig'))
    check=check_native_plan(report.get('native_baseline',[]),plan,facts,report.get('native_bindings'))
    if sha256(facts['path'])!=facts['sha256'] or report.get('reopen',{}).get('status')!='PASS' or check['layout_flags']:raise ValueError('Native/source/layout gate failed')
    coverage=check_coverage(plan,facts)
    if not coverage['complete']:raise ValueError('Incomplete geometry definitions')
    report.update(native_plan_check=check,layout_flags=check['layout_flags'],coverage_check=coverage)
    return report

def verify_outputs(plan,report):
    import json
    from validate_plan import check_coverage
    verify_native(plan,report);check_upstream(report,True)
    facts=json.loads(Path(plan['facts']).read_text(encoding='utf-8-sig'))
    coverage=check_coverage(plan,facts)
    native_plan=report['native_plan_check']
    export=report.get('export',{})
    viewer=export.get('viewer',{})
    if export.get('status')!='DWG_EXPORTED' or viewer.get('status')!='PDF_PRINTED_REVIEW_REQUIRED':raise ValueError('DWG/PDF export was not verified')
    if sha256(plan['output_dwg'])!=viewer.get('pdf_source_dwg_sha256') or sha256(plan['output_pdf'])!=viewer.get('pdf_sha256'):raise ValueError('PDF source DWG identity mismatch')
    if not Path(plan['output_dwg']).read_bytes().startswith(b'AC10'):raise ValueError('Invalid DWG header')
    if not export.get('settings_restored'):raise ValueError('Export settings not restored')
    if viewer.get('method')!='EDRAWINGS_DWG_DIRECT' or viewer.get('viewer',{}).get('sheet_count')!=1 or not viewer.get('viewer',{}).get('owned_viewer_document_closed'):raise ValueError('Independent DWG readback incomplete')
    fidelity={'status':'VISUAL_COMPARISON_REQUIRED','method':'EDRAWINGS_DWG_DIRECT','associative_dimensions':'NOT_VERIFIED'}
    delivery_files(Path(plan['output_pdf']).parent)
    texts=[item['text'] for item in plan['notes']+plan['labels']]
    texts.extend(cell for table in plan['tables'] for row in table['rows'] for cell in row if cell.strip())
    texts.extend(str(x['expected_mm']).rstrip('0').rstrip('.') if isinstance(x['expected_mm'],float) else str(x['expected_mm']) for key in ('dimensions','diameters') for x in plan.get(key,[]))
    pdf=check_pdf(plan['output_pdf'],[plan['sheet']['width_mm'],plan['sheet']['height_mm']],texts)
    source_ok=sha256(facts['path'])==facts['sha256']
    native_ok=source_ok and report.get('reopen',{}).get('status')=='PASS' and not report.get('layout_flags')
    review_path=Path(plan['output_drawing']).parent/'visual-review.json'
    visual_ok=check_visual_review(json.loads(review_path.read_text(encoding='utf-8-sig')),plan['output_dwg'],plan['output_pdf']) if review_path.exists() else False
    report.update(status=final_status(native_ok,True,visual_ok,coverage['complete']),coverage_check=coverage,pdf_check=pdf,readback_check=fidelity,native_plan_check=native_plan,visual_review='PASS' if visual_ok else 'NOT_CHECKED',manufacturing_release='NOT_APPROVED')
    if not native_ok:report['error']='Source/native/layout verification failed'
    if not coverage['complete']:report['error']='Incomplete geometry: '+repr(coverage['incomplete'])
    return report

if __name__=='__main__':
    import json,sys
    try:
        plan=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        report=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8-sig'))
        print(json.dumps(verify_native(plan,report) if '--native-only' in sys.argv else verify_outputs(plan,report),ensure_ascii=False))
    except Exception as exc:print('OUTPUT_FAILED: '+str(exc));sys.exit(1)
