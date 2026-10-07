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
    if plan.get('details'):raise ValueError('Native detail view backend is not implemented')
    if plan.get('dimension_scheme'):raise ValueError('Auto Dimension Scheme requires verified explicit-rule backend; do not apply default tolerances')
    if plan.get('style') or plan.get('export'):raise ValueError('Unimplemented style/export overrides; use the selected template and explicit backend')
    if type(plan.get('import_pmi',False)) is not bool or type(plan.get('auto_arrange',False)) is not bool:raise ValueError('PMI/arrange options must be booleans')
    orthos=[v['scale'] for v in plan.get('views',[]) if not any(s in v['model_view'].lower() for s in ('isometric','等轴','等軸'))]
    if orthos and any(x!=orthos[0] for x in orthos):raise ValueError('Related orthographic views require the same scale')
    model=plan.get('model_dimensions',{})
    if set(model)-{'keep','include_unmarked','positions'}:raise ValueError('Unknown model dimension options')
    if type(model.get('include_unmarked',False)) is not bool:raise ValueError('include_unmarked must be boolean')
    keep=model.get('keep',[])
    if len(set(keep))!=len(keep) or any(not isinstance(x,str) or not x.strip() for x in keep):raise ValueError('Invalid retained model dimension identity')
    seen=set()
    for item in model.get('positions',[]):
        if item['name'] not in keep or item['name'] in seen:raise ValueError('Placement requires unique retained model dimension')
        seen.add(item['name']);xy=item['position_mm'];sh=plan['sheet']
        if len(xy)!=2 or any(type(x) not in (float,int) or not math.isfinite(x) for x in xy) or not (0<xy[0]<sh['width_mm'] and 0<xy[1]<sh['height_mm']):raise ValueError('Invalid model dimension position')

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
    allowed={'version','facts','output_drawing','output_dwg','output_pdf','template','sheet','views','dimensions','diameters','sections','details','labels','tables','notes','unresolved','coverage','dimension_ids','model_dimensions','import_pmi','auto_arrange','linear','radial','export','style','dimension_scheme'}
    if set(plan)-allowed:raise ValueError('Unknown fields: '+str(set(plan)-allowed))
    check_supported(plan)
    facts=facts or json.loads(Path(plan['facts']).read_text(encoding='utf-8-sig'))
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
