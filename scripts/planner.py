"""Bounded paper/scale search. Coordinates are millimetres, text size stays fixed."""
import math

PAPERS = {'A4':(297,210), 'A3':(420,297), 'A2':(594,420)}
SCALES = (2,1.5,1,0.75,0.5,0.2,0.1,0.05)

def overlaps(a,b):
    return min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])

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
