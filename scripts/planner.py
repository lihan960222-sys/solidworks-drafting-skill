"""Bounded paper/scale search. Coordinates are millimetres, text size stays fixed."""
import math
import itertools

PAPERS = {'A4':(297,210), 'A3':(420,297), 'A2':(594,420)}
SCALES = (2,1.5,1,0.75,0.5,0.2,0.1,0.05)

def overlaps(a,b):
    return min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])

def pack_envelopes(blocks, first_angle, usable_bounds_mm, table_sizes_mm=None,
                   reserved_boxes_mm=None, gap_mm=12, orthographic_views=None):
    """Translate measured asymmetric blocks. No scaling, annotation removal or rotation.

    Keep the orthographic centres aligned; pack supporting blocks around that group.
    This bounded corner/grid search can reject a layout a general packing solver finds.
    """
    def box_ok(box):
        return len(box)==4 and all(type(x) in (int,float) and math.isfinite(x) for x in box) and box[0]<box[2] and box[1]<box[3]
    if type(first_angle) is not bool or not box_ok(usable_bounds_mm) or not math.isfinite(gap_mm) or gap_mm<0:
        raise ValueError('Invalid envelope layout bounds/projection/gap')
    roles=orthographic_views or {k:k for k in ('front','top','right') if k in blocks}
    if 'front' not in roles or roles['front'] not in blocks or len(set(roles.values()))!=len(roles):
        raise ValueError('Envelope layout requires unique orthographic view roles')
    local={}
    for key,block in blocks.items():
        p=block['position_mm'];b=block['bounds_mm']
        if not box_ok(b) or len(p)!=2 or any(not math.isfinite(v) for v in p):raise ValueError('Invalid measured envelope')
        local[key]=[b[0]-p[0],b[1]-p[1],b[2]-p[0],b[3]-p[1]]
    ux,uy,ur,ut=usable_bounds_mm
    tables=[];ty=ut
    for tw,th in table_sizes_mm or []:
        if not all(math.isfinite(x) and x>0 for x in (tw,th)):raise ValueError('Invalid table extent')
        table=[ur-tw,ty-th,ur,ty];tables.append(table);ty-=th+gap_mm
    obstacles=list(reserved_boxes_mm or [])
    if any(not box_ok(b) for b in obstacles):raise ValueError('Invalid reserved box')
    def inside(b):return ux-1e-8<=b[0] and uy-1e-8<=b[1] and b[2]<=ur+1e-8 and b[3]<=ut+1e-8
    def clear(b,others):
        return inside(b) and all(not overlaps([b[0]-gap_mm/2,b[1]-gap_mm/2,b[2]+gap_mm/2,b[3]+gap_mm/2],
                                            [r[0]-gap_mm/2,r[1]-gap_mm/2,r[2]+gap_mm/2,r[3]+gap_mm/2]) for r in others)
    if any(not inside(b) or any(overlaps(b,r) for r in obstacles) for b in tables):raise ValueError('Tables do not fit upper-right region')
    obstacles+=tables
    front=roles['front'];f=local[front];centres={front:[0,0]}
    if 'right' in roles:
        key=roles['right'];b=local[key]
        centres[key]=[f[0]-gap_mm-b[2] if first_angle else f[2]+gap_mm-b[0],0]
    if 'top' in roles:
        key=roles['top'];b=local[key]
        centres[key]=[0,f[1]-gap_mm-b[3] if first_angle else f[3]+gap_mm-b[1]]
    def translated(key,p):
        b=local[key];return [b[0]+p[0],b[1]+p[1],b[2]+p[0],b[3]+p[1]]
    group={k:translated(k,p) for k,p in centres.items()}
    # Nonadjacent top/side blocks may have asymmetric annotations that collide.
    if any(overlaps(a,b) for a,b in itertools.combinations(group.values(),2)):
        raise ValueError('Orthographic annotation envelopes do not fit aligned group')
    gb=[min(b[0] for b in group.values()),min(b[1] for b in group.values()),
        max(b[2] for b in group.values()),max(b[3] for b in group.values())]
    extra=sorted(set(blocks)-set(centres),key=lambda k:-(local[k][2]-local[k][0])*(local[k][3]-local[k][1]))
    def candidates(b,occupied):
        w=b[2]-b[0];h=b[3]-b[1]
        xs={ux,ur-w,(ux+ur-w)/2};ys={uy,ut-h,(uy+ut-h)/2}
        for r in occupied:
            xs.update((r[0]-gap_mm-w,r[2]+gap_mm));ys.update((r[1]-gap_mm-h,r[3]+gap_mm))
        xs.update(ux+i*5 for i in range(max(0,int((ur-ux-w)/5)+1)))
        ys.update(uy+i*5 for i in range(max(0,int((ut-uy-h)/5)+1)))
        return sorted(((x,y) for x in xs for y in ys if inside([x,y,x+w,y+h])),
                      key=lambda p:(p[0]-(ux+ur-w)/2)**2+(p[1]-(uy+ut-h)/2)**2)
    for gx,gy in candidates(gb,obstacles):
        delta=[gx-gb[0],gy-gb[1]]
        pos={k:[p[0]+delta[0],p[1]+delta[1]] for k,p in centres.items()}
        boxes={k:translated(k,p) for k,p in pos.items()}
        if any(not clear(b,obstacles) for b in boxes.values()):continue
        occupied=list(boxes.values())+obstacles
        for key in extra:
            found=False
            for x,y in candidates(local[key],occupied):
                p=[x-local[key][0],y-local[key][1]];b=translated(key,p)
                if clear(b,occupied):pos[key]=p;boxes[key]=b;occupied.append(b);found=True;break
            if not found:break
        else:
            content=list(boxes.values())+tables
            area=sum((b[2]-b[0])*(b[3]-b[1]) for b in content)
            cb=[min(b[0] for b in content),min(b[1] for b in content),max(b[2] for b in content),max(b[3] for b in content)]
            return {'positions_mm':pos,'bounds_mm':boxes,'table_bounds_mm':tables,
                    'table_positions_mm':[[b[0],b[3]] for b in tables],
                    'group_bounds_mm':[gx,gy,gx+gb[2]-gb[0],gy+gb[3]-gb[1]],
                    'method':'MEASURED_ANNOTATION_ENVELOPES','scale_changed':False,
                    'occupied_fraction':area/((ur-ux)*(ut-uy)),
                    'balance_offset_mm':[(cb[0]+cb[2]-ux-ur)/2,(cb[1]+cb[3]-uy-ut)/2]}
    raise ValueError('Measured annotation envelopes do not fit; retain dimensions and revise scale/views/lanes')


if __name__=='__main__':
    import json,sys
    data=json.load(sys.stdin)
    print(json.dumps(pack_envelopes(**data)))

def unique_definitions(items):
    seen=set(); result=[]
    for item in items:
        key=(item['entity'],item['meaning'],item.get('direction'))
        if key not in seen:seen.add(key);result.append(item)
    return result

def candidate_layouts(view_sizes, first_angle, annotation_margin_mm=8, table_size_mm=None, fixed_sheet_mm=None, usable_bounds_mm=None, reserved_boxes_mm=None):
    if type(first_angle) is not bool:raise ValueError('Explicit projection required')
    if 'front' not in view_sizes:raise ValueError('front view required')
    if any(len(x)!=2 or any(not math.isfinite(v) or v<=0 for v in x) for x in view_sizes.values()):raise ValueError('Invalid projected view extent')
    if not math.isfinite(annotation_margin_mm) or annotation_margin_mm<0:raise ValueError('Invalid annotation margin')
    if table_size_mm and (len(table_size_mm)!=2 or any(not math.isfinite(x) or x<=0 for x in table_size_mm)):raise ValueError('Invalid table extent')
    if fixed_sheet_mm and sorted(fixed_sheet_mm) not in [sorted(x) for x in PAPERS.values()]:raise ValueError('Unsupported template paper')
    if usable_bounds_mm and not fixed_sheet_mm:raise ValueError('Template bounds require a fixed sheet')
    results=[];gap=12;margin=annotation_margin_mm
    for paper,landscape in PAPERS.items():
        for width,height in (landscape,landscape[::-1]):
            if fixed_sheet_mm and [width,height]!=list(fixed_sheet_mm):continue
            usable=usable_bounds_mm or [10,45,width-10,height-10]
            ux,uy,ur,ut=usable;uw=ur-ux;uh=ut-uy
            if not(0<=ux<ur<=width and 0<=uy<ut<=height):raise ValueError('Invalid template usable bounds')
            title=[max(10,width-190),10,width-10,35]
            reserved=reserved_boxes_mm or [title]
            for scale in SCALES:
                sizes={key:[a*scale+2*margin,b*scale+2*margin] for key,(a,b) in view_sizes.items()}
                front=sizes['front'];side=sizes.get('right',[0,0]);top=sizes.get('top',[0,0])
                row_w=front[0]+(side[0]+gap if side[0] else 0)
                row_h=front[1]+(top[1]+gap if top[1] else 0)
                extra=[key for key in sizes if key not in ('front','right','top')]
                total_h=row_h+sum(sizes[key][1]+gap for key in extra)
                group_w=max([row_w]+[sizes[key][0] for key in extra])
                placements=('side','bottom') if table_size_mm else ('none',)
                for placement in placements:
                    tw,th=table_size_mm or (0,0)
                    full_w=group_w+(tw+gap if placement=='side' else 0)
                    full_h=max(total_h,th) if placement=='side' else total_h+(th+gap if placement=='bottom' else 0)
                    if full_w>uw or full_h>uh or tw>uw:continue
                    left=ux+(uw-full_w)/2
                    bottom=uy+(uh-full_h)/2+(th+gap if placement=='bottom' else 0)
                    fx=left+front[0]/2+(side[0]+gap if first_angle and side[0] else 0)
                    fy=bottom+front[1]/2+(top[1]+gap if first_angle and top[1] else 0)
                    positions={'front':[fx,fy]}
                    if side[0]:positions['right']=[fx+(-1 if first_angle else 1)*(front[0]/2+gap+side[0]/2),fy]
                    if top[1]:positions['top']=[fx,fy+(-1 if first_angle else 1)*(front[1]/2+gap+top[1]/2)]
                    y=bottom+row_h
                    for key in extra:
                        y+=gap+sizes[key][1]/2;positions[key]=[left+group_w/2,y];y+=sizes[key][1]/2
                    boxes={key:[x-sizes[key][0]/2,y-sizes[key][1]/2,x+sizes[key][0]/2,y+sizes[key][1]/2] for key,(x,y) in positions.items()}
                    if any(overlaps(box,r) for box in boxes.values() for r in reserved):continue
                    result={'paper':paper,'sheet_mm':[width,height],'scale':scale,'first_angle':first_angle,'positions_mm':positions,'reserved_bounds_mm':boxes,'title_block_mm':title,'font_mm':3.5,'table_placement':placement}
                    if table_size_mm:
                        tx=left+group_w+gap if placement=='side' else ux
                        ty=bottom+full_h if placement=='side' else bottom-gap
                        table_box=[tx,ty-th,tx+tw,ty]
                        if any(overlaps(table_box,r) for r in reserved) or any(overlaps(table_box,box) for box in boxes.values()):continue
                        result.update(table_position_mm=[tx,ty],table_bounds_mm=table_box)
                    result['content_envelope_fill']=full_w*full_h/(uw*uh)
                    result['template_reserved_mm']=reserved
                    results.append(result)
    return sorted(results,key=lambda x:(x['sheet_mm'][0]*x['sheet_mm'][1],-x['scale'],-x['content_envelope_fill']))
