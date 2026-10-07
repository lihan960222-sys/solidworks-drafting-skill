"""v2 provenance and coverage checks layered on bundled native validation."""
import json
import math
import os
from pathlib import Path

def check_table(table):
    required=('role','feature_ids','units','rows','row_evidence')
    if any(key not in table for key in required):raise ValueError('Table missing identity/units/evidence')
    if table['role'] not in ('nominal_hole_schedule','nominal_feature_schedule'):raise ValueError('Unsupported table role')
    ids=table['feature_ids']
    if not ids or len(set(ids))!=len(ids) or len(ids)!=len(table['rows'])-1 or len(table['row_evidence'])!=len(ids):raise ValueError('Invalid table row identity/evidence')
    if not table['units'] or any(not x for x in table['row_evidence']):raise ValueError('Missing table units/evidence')
    if any(str(ident)!=str(row[0]) for ident,row in zip(ids,table['rows'][1:])):raise ValueError('Table identifier disagrees with row')
    if table['role']=='nominal_hole_schedule' and (len(table.get('origin',[]))!=3 or len(table.get('axes',[]))!=2):raise ValueError('Hole table requires coordinate origin/axes')

def check_hole_geometry(table,facts,labels):
    if table['role']!='nominal_hole_schedule':return
    if table['axes']!=['X','Y'] or table['units']!='mm':raise ValueError('Verified hole schedule currently requires global X/Y axes in mm')
    headers={''.join(x.lower().split()):i for i,x in enumerate(table['rows'][0])}
    required=('id','x(mm)','y(mm)','d(mm)','depth')
    if any(x not in headers for x in required) or not ('qty' in headers or 'count' in headers):raise ValueError('Hole schedule needs ID, X/Y/D (mm), Depth and Qty/Count columns')
    edges={e['id']:e for e in facts['edges']};mapped={x['text']:x['edge_id'] for x in labels};origin=table['origin']
    def equal(a,b):return abs(float(a)-b)<1e-4
    for ident,row,evidence in zip(table['feature_ids'],table['rows'][1:],table['row_evidence']):
        if not isinstance(evidence,str) or not evidence.startswith('edges:') or not evidence[6:].isdigit():raise ValueError('Hole row requires an exact edges:<id> geometry reference')
        edge_id=int(evidence[6:]);edge=edges.get(edge_id)
        if not edge or edge['type']!='circle' or mapped.get(ident)!=edge_id:raise ValueError('Hole row/visible label geometry mismatch')
        cp=edge['parameters_si']
        if abs(abs(cp[5])-1)>1e-7:raise ValueError('Hole schedule circle is not normal to X/Y plane')
        if not equal(row[headers['x(mm)']],cp[0]*1000-origin[0]) or not equal(row[headers['y(mm)']],cp[1]*1000-origin[1]):raise ValueError('Hole coordinate disagrees with source circle')
        if not equal(row[headers['d(mm)']],cp[6]*2000):raise ValueError('Hole diameter disagrees with source circle')
        if row[headers.get('qty',headers.get('count'))]!='1':raise ValueError('One individually labelled hole per row; grouped quantities need a verified pattern backend')
        cylinders=[f for f in facts.get('faces',[]) if f['body']==edge['body'] and f['type']=='cylinder' and all(abs(f['parameters_si'][i]-cp[i])<1e-7 for i in (0,1,6)) and abs(abs(f['parameters_si'][5])-1)<1e-7]
        if not cylinders:raise ValueError('Hole depth lacks matching cylindrical face')
        depth=row[headers['depth']].upper();body=next(b for b in facts['bodies'] if b['id']==edge['body'])
        if depth=='THRU':
            if not any(equal(f['bounds_si'][2]*1000,body['bounds_si'][2]*1000) and equal(f['bounds_si'][5]*1000,body['bounds_si'][5]*1000) for f in cylinders):raise ValueError('THRU not established by continuous cylindrical face')
        elif not any(equal(depth,(f['bounds_si'][5]-f['bounds_si'][2])*1000) for f in cylinders):raise ValueError('Hole depth disagrees with cylindrical geometry')

def check_coverage(plan,facts):
    if not facts.get('draft_features'):raise ValueError('Empty feature inventory cannot prove coverage')
    items={x['feature']:x for x in plan.get('coverage',[])}
    if len(items)!=len(plan.get('coverage',[])):raise ValueError('Duplicate feature coverage')
    known={x['id'] for x in facts['draft_features']}
    if set(items)-known:raise ValueError('Unknown supplemental geometry must be added to the explicit facts inventory: '+str(set(items)-known))
    ids=set(plan.get('dimension_ids',[])); incomplete=[]
    for feature in facts.get('draft_features',[]):
        ident=feature['id']
        if ident not in items:raise ValueError('Missing feature coverage: '+ident)
        item=items[ident]
        if item['status'] in ('unsupported_operation','missing_geometry_definition'):
            if not item.get('reason'):raise ValueError('Incomplete feature needs reason')
            incomplete.append(ident);continue
        if item['status']!='covered':raise ValueError('Invalid geometry coverage state')
        for name in feature['required']:
            field=item.get('fields',{}).get(name)
            if not field:raise ValueError('Missing geometry definition '+ident+': '+name)
            if not field.get('evidence') or not field.get('unit') or field.get('annotation') not in ids:raise ValueError('Unproven feature field '+name)
            if 'value' not in field or isinstance(field['value'],float) and not math.isfinite(field['value']):raise ValueError('Invalid feature field value')
    return {'complete':not incomplete,'incomplete':incomplete,'features_checked':len(facts.get('draft_features',[]))}

def check_supported(plan):
    check_layout_options(plan)
    if plan.get('details'):raise ValueError('Native detail view backend is not implemented')
    if plan.get('dimension_scheme'):raise ValueError('Auto Dimension Scheme requires verified explicit-rule backend; do not apply default tolerances')
    if plan.get('style') or plan.get('export'):raise ValueError('Unimplemented style/export overrides; use the selected template and explicit backend')
    if type(plan.get('import_pmi',False)) is not bool or type(plan.get('auto_arrange',False)) is not bool:raise ValueError('PMI/arrange options must be booleans')
    orthos=[v['scale'] for v in plan.get('views',[]) if not any(s in v['model_view'].lower() for s in ('isometric','等轴','等軸'))]
    if orthos and any(x!=orthos[0] for x in orthos):raise ValueError('Related orthographic views require the same scale')
    model=plan.get('model_dimensions',{})
    if set(model)-{'keep','include_unmarked','include_hidden_features','positions'}:raise ValueError('Unknown model dimension options')
    for option in ('include_unmarked','include_hidden_features'):
        if type(model.get(option,False)) is not bool:raise ValueError(option+' must be boolean')
    keep=model.get('keep',[])
    if len(set(keep))!=len(keep) or any(not isinstance(x,str) or not x.strip() for x in keep):raise ValueError('Invalid retained model dimension identity')
    seen=set()
    for item in model.get('positions',[]):
        if item['name'] not in keep or item['name'] in seen:raise ValueError('Placement requires unique retained model dimension')
        seen.add(item['name']);xy=item['position_mm'];sh=plan['sheet']
        if len(xy)!=2 or any(type(x) not in (float,int) or not math.isfinite(x) for x in xy) or not (0<xy[0]<sh['width_mm'] and 0<xy[1]<sh['height_mm']):raise ValueError('Invalid model dimension position')

def check_layout_options(plan):
    if type(plan.get('line_hierarchy',True)) is not bool:raise ValueError('line_hierarchy must be boolean')
    if 'layout' not in plan:return
    layout=plan['layout'];keys={'usable_bounds_mm','reserved_boxes_mm','orthographic_views','gap_mm','padding_mm'}
    if not isinstance(layout,dict) or not keys<=set(layout) or set(layout)-keys-{'scale_factors','fill_range','target_fill'}:raise ValueError('Invalid measured layout fields')
    sh=plan['sheet']
    def box(b):return isinstance(b,list) and len(b)==4 and all(type(x) in (int,float) and math.isfinite(x) for x in b) and 0<=b[0]<b[2]<=sh['width_mm'] and 0<=b[1]<b[3]<=sh['height_mm']
    if not box(layout['usable_bounds_mm']) or not isinstance(layout['reserved_boxes_mm'],list) or any(not box(b) for b in layout['reserved_boxes_mm']):raise ValueError('Invalid template layout bounds')
    for k in ('gap_mm','padding_mm'):
        if type(layout[k]) not in (int,float) or not math.isfinite(layout[k]) or layout[k]<0:raise ValueError('Invalid layout '+k)
    factors=layout.get('scale_factors',[1,.95,.9,.85,.8,.75,.625,.5,.375,.25,.2,.125])
    if not isinstance(factors,list) or not factors or len(factors)>12 or factors[0]!=1 or any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in factors) or any(a<=b for a,b in zip(factors,factors[1:])):raise ValueError('Invalid descending layout scale_factors')
    fill=layout.get('fill_range',[.45,.65]);target=layout.get('target_fill',.55)
    if not isinstance(fill,list) or len(fill)!=2 or type(target) not in (int,float) or not math.isfinite(target) or any(type(x) not in (int,float) or not math.isfinite(x) for x in fill) or not 0<fill[0]<=target<=fill[1]<1:raise ValueError('Invalid layout fill target/range')
    roles=layout['orthographic_views'];views={v['id'] for v in plan.get('views',[])}
    if not isinstance(roles,dict) or 'front' not in roles or set(roles)-{'front','top','right'} or not set(roles.values())<=views or len(set(roles.values()))!=len(roles):raise ValueError('Invalid orthographic view roles')

def dimension_key(name):
    return '@'.join(name.split('@')[:2])

def check_model_dimensions(plan,facts):
    keep=plan.get('model_dimensions',{}).get('keep',[])
    keys=[dimension_key(name) for name in keep]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate aliases refer to the same model dimension')
    names={d['name'] for f in facts.get('features',[]) for d in f.get('dimensions',[])}
    known={dimension_key(name) for name in names}
    for name in keep:
        if name not in names and name not in known:raise ValueError('Selected dimension is absent from source facts: '+name)

def check_geometry_audit(plan,facts):
    """Check the recorded geometric proof, not automatic reconstruction of a B-rep."""
    audit=plan.get('geometry_audit')
    if not isinstance(audit,dict):raise ValueError('Missing geometric completeness audit')
    if audit.get('scope')!='nominal_geometry' or audit.get('source_sha256')!=facts.get('sha256'):raise ValueError('Geometry audit source/scope mismatch')
    for key in ('missing_definitions','redundant_definitions'):
        if not isinstance(audit.get(key),list) or audit[key]:raise ValueError('Incomplete or redundant geometry audit: '+key)
    checks=('feature_inventory','sizes','locations','orientations','depths_and_sections','patterns_and_relations','dimension_chains','nonredundancy','reconstruction')
    for key in checks:
        check=audit.get('checks',{}).get(key,{})
        if check.get('passed') is not True or not isinstance(check.get('evidence'),str) or not check['evidence'].strip():raise ValueError('Unproven geometry audit check: '+key)
    definitions=audit.get('definitions',[])
    if not isinstance(definitions,list) or not definitions:raise ValueError('Empty geometry audit definitions')
    by_id={};semantic=set();bound=set();ids=set(plan.get('dimension_ids',[]))
    for d in definitions:
        if any(not isinstance(d.get(k),str) or not d[k].strip() for k in ('id','entity','property','frame','evidence')):raise ValueError('Incomplete geometric definition identity/evidence')
        key=(d['entity'],d['property'],d['frame'])
        if d['id'] in by_id or key in semantic:raise ValueError('Duplicate geometric definition: '+d['id'])
        by_id[d['id']]=d;semantic.add(key)
        if d.get('annotation'):
            if d['annotation'] not in ids or d.get('depends_on'):raise ValueError('Driving definition requires one planned annotation and no derived dependency')
            bound.add(d['annotation'])
        elif not isinstance(d.get('depends_on'),list) or not d['depends_on'] or not isinstance(d.get('equation'),str) or not d['equation'].strip():raise ValueError('Derived definition requires dependencies and explicit equation')
    active=set();done=set()
    def visit(ident):
        if ident not in by_id:raise ValueError('Unknown geometric dependency: '+str(ident))
        if ident in active:raise ValueError('Geometry dimension-chain cycle: '+ident)
        if ident in done:return
        active.add(ident)
        for dep in by_id[ident].get('depends_on',[]):visit(dep)
        active.remove(ident);done.add(ident)
    for ident in by_id:visit(ident)
    driving={x['id'] for k in ('dimensions','diameters','linear','radial') for x in plan.get(k,[])}
    driving.update('model:'+n for n in plan.get('model_dimensions',{}).get('keep',[]))
    driving.update('table:'+n for t in plan.get('tables',[]) for n in t['feature_ids'])
    if driving-bound:raise ValueError('Unmapped driving dimensions in geometry audit: '+str(sorted(driving-bound)))
    return {'status':'PASS','definitions_checked':len(definitions),'driving_annotations_checked':len(driving),'method':'RECORDED_AGENT_GEOMETRY_REVIEW','automatic_reconstruction':False}

def check_experimental(plan,facts):
    views={v['id'] for k in ('views','sections') for v in plan.get(k,[])};edges={e['id']:e for e in facts['edges']};sh=plan['sheet']
    for key in ('linear','radial'):
        if not isinstance(plan.get(key,[]),list):raise ValueError(key+' must be an array')
        for item in plan.get(key,[]):
            required={'id','view','position_mm','evidence','a_edge','b_edge','direction'} if key=='linear' else {'id','view','position_mm','evidence','edge_id'}
            expected='expected_deg' if item.get('direction')=='angular' else 'expected_mm';required.add(expected)
            if set(item)!=required:raise ValueError('Invalid experimental operation fields')
            if item['view'] not in views or not item['evidence'] or not isinstance(item['id'],str) or not item['id']:raise ValueError('Invalid experimental identity/view/evidence')
            if key=='linear' and item['direction'] not in ('horizontal','vertical','angular'):raise ValueError('Invalid experimental direction')
            value=item[expected];xy=item['position_mm']
            if type(value) not in (int,float) or not math.isfinite(value) or value<=0:raise ValueError('Invalid experimental expected value')
            if len(xy)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in xy) or not (0<xy[0]<sh['width_mm'] and 0<xy[1]<sh['height_mm']):raise ValueError('Experimental position outside sheet')
            for field in ('a_edge','b_edge') if key=='linear' else ('edge_id',):
                edge=edges.get(item[field])
                if type(item[field]) is not int or not edge or not edge.get('persist_ref') or edge['type'] not in (('line','circle') if key=='linear' else ('circle',)):raise ValueError('Invalid persistent experimental edge')
            if key=='linear' and item['a_edge']==item['b_edge']:raise ValueError('Two distinct edges required')

def validate(plan, facts=None, allow_existing=False):
    if plan.get('version')!=2:raise ValueError('Expected drafting plan v2')
    allowed={'version','facts','output_drawing','output_dwg','output_pdf','template','sheet','views','dimensions','diameters','sections','details','labels','tables','notes','unresolved','coverage','dimension_ids','model_dimensions','import_pmi','auto_arrange','linear','radial','export','style','dimension_scheme','geometry_audit','layout','line_hierarchy'}
    if set(plan)-allowed:raise ValueError('Unknown fields: '+str(set(plan)-allowed))
    check_supported(plan)
    facts=facts or json.loads(Path(plan['facts']).read_text(encoding='utf-8-sig'))
    check_model_dimensions(plan,facts)
    check_experimental(plan,facts)
    for key,suffix in (('output_drawing','.slddrw'),('output_dwg','.dwg'),('output_pdf','.pdf')):
        value=plan.get(key,'')
        if not os.path.isabs(value) or not value.lower().endswith(suffix):raise ValueError('Invalid '+key)
        if not allow_existing and Path(value).exists():raise ValueError('Existing output refused: '+value)
    if Path(plan['output_dwg']).parent != Path(plan['output_pdf']).parent:raise ValueError('Deliverable directory mismatch')
    if Path(plan['output_drawing']).parent==Path(plan['output_pdf']).parent:raise ValueError('Native drawing belongs in internal directory')
    sheet=plan['sheet'];size=sorted([sheet['width_mm'],sheet['height_mm']])
    if size not in ([210,297],[297,420],[420,594]):raise ValueError('Only single A4/A3/A2 supported')
    if plan.get('dimension_scheme'):raise ValueError('Auto Dimension Scheme requires verified explicit-rule backend; do not apply default tolerances')
    ids=plan.get('dimension_ids',[])
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate annotation ID')
    operations=[x for key in ('dimensions','diameters','linear','radial','labels','notes','details') for x in plan.get(key,[])]
    actual={x['id'] for x in operations if 'id' in x}
    if len(actual)!=len(operations):raise ValueError('Operation IDs must be present and unique')
    for table in plan.get('tables',[]):
        check_table(table);check_hole_geometry(table,facts,plan.get('labels',[]));actual.update('table:'+x for x in table['feature_ids'])
    actual.update('model:'+x for x in plan.get('model_dimensions',{}).get('keep',[]))
    if set(ids)!=actual:raise ValueError('Annotation IDs must match planned operations')
    for table in plan.get('tables',[]):
        visible={x['text'] for x in plan.get('labels',[])}
        if not set(table['feature_ids'])<=visible:raise ValueError('Table row needs visible feature label')
    # Both validators are bundled. Native validation is repeated before worker mutation.
    from validate_native import validate as native_validate
    native_validate(plan,allow_existing=allow_existing)
    coverage=check_coverage(plan,facts)
    return {'status':'VALID','coverage':coverage}

if __name__=='__main__':
    import sys
    try:print(json.dumps(validate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')),allow_existing='--allow-existing' in sys.argv),ensure_ascii=False))
    except Exception as exc:print('INVALID: '+str(exc),file=sys.stderr);sys.exit(1)
