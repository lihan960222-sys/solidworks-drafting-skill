import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import planner
import verify_outputs
import validate_plan
import copy


class EnvelopeLayoutTests(unittest.TestCase):
    def blocks(self):
        return {'front': {'position_mm':[180,150], 'bounds_mm':[115,95,235,185]},
                'top': {'position_mm':[180,65], 'bounds_mm':[120,35,240,90]},
                'right': {'position_mm':[75,150], 'bounds_mm':[45,100,100,190]},
                'iso': {'position_mm':[300,100], 'bounds_mm':[270,65,335,135]}}

    def test_asymmetric_annotation_blocks_keep_projection_alignment(self):
        for first in (True, False):
            result=planner.pack_envelopes(self.blocks(), first, [25,65,415,292],
                                         table_sizes_mm=[[115,49]], gap_mm=12)
            pos=result['positions_mm']; boxes=result['bounds_mm']
            self.assertEqual(pos['front'][0],pos['top'][0])
            self.assertEqual(pos['front'][1],pos['right'][1])
            self.assertEqual(pos['right'][0]<pos['front'][0],first)
            self.assertEqual(pos['top'][1]<pos['front'][1],first)
            self.assertEqual(result['table_bounds_mm'][0],[300,243,415,292])
            all_boxes=list(boxes.values())+result['table_bounds_mm']
            for i,a in enumerate(all_boxes):
                self.assertTrue(25<=a[0]<a[2]<=415 and 65<=a[1]<a[3]<=292)
                for b in all_boxes[i+1:]:self.assertFalse(planner.overlaps(a,b))
            for name,block in self.blocks().items():
                moved=boxes[name]; old=block['bounds_mm']
                self.assertAlmostEqual(moved[2]-moved[0],old[2]-old[0])
                self.assertAlmostEqual(moved[3]-moved[1],old[3]-old[1])

    def test_oversized_annotation_block_fails_without_deleting_dimensions(self):
        with self.assertRaisesRegex(ValueError,'fit'):
            planner.pack_envelopes({'front':{'position_mm':[0,0],'bounds_mm':[-400,-20,400,20]}},True,[25,65,415,292])

    def test_nonadjacent_orthographic_blocks_require_full_clearance(self):
        blocks=self.blocks()
        blocks['top']['bounds_mm'][0]=90
        blocks['right']['bounds_mm'][1]=89
        for first_angle in (True,False):
            result=planner.pack_envelopes(blocks,first_angle,[25,65,415,292],gap_mm=12)
            boxes=list(result['bounds_mm'].values())
            for i,a in enumerate(boxes):
                for b in boxes[i+1:]:
                    self.assertGreaterEqual(max(a[0]-b[2],b[0]-a[2],a[1]-b[3],b[1]-a[3]),12-1e-8)

    def test_reserved_stamp_and_table_stack_are_obstacles(self):
        result=planner.pack_envelopes(self.blocks(),True,[25,65,415,292],
                                     table_sizes_mm=[[80,30],[60,20]], reserved_boxes_mm=[[25,65,65,100]])
        self.assertEqual(result['table_bounds_mm'][0],[335,262,415,292])
        self.assertEqual(result['table_bounds_mm'][1],[355,230,415,250])
        for box in result['bounds_mm'].values():self.assertFalse(planner.overlaps(box,[25,65,65,100]))

    def test_invalid_template_bounds_and_roles_fail_preflight(self):
        plan={'sheet':{'width_mm':420,'height_mm':297},'views':[{'id':'front'}],
              'layout':{'usable_bounds_mm':[25,65,415,292],'reserved_boxes_mm':[],
                        'orthographic_views':{'front':'missing'},'gap_mm':12,'padding_mm':2}}
        with self.assertRaisesRegex(ValueError,'roles'):validate_plan.check_layout_options(plan)
        plan['layout']['orthographic_views']={'front':'front'}
        validate_plan.check_layout_options(plan)
        plan['layout']['usable_bounds_mm'][2]=450
        with self.assertRaisesRegex(ValueError,'bounds'):validate_plan.check_layout_options(plan)

    def test_native_crlf_note_has_same_content_as_lf_plan(self):
        p={'sheet':{'width_mm':420,'height_mm':297},'views':[], 'notes':[{'text':'Origin\nAxes'}]}
        verify_outputs.check_native_plan([{'source':'','annotations':[{'text':'Origin\r\nAxes'}]}],p,{})

    def test_scale_trials_and_occupation_targets_are_bounded_and_ordered(self):
        p={'sheet':{'width_mm':420,'height_mm':297},'views':[{'id':'front'}],
           'layout':{'usable_bounds_mm':[35,70,405,282],'reserved_boxes_mm':[],
                     'orthographic_views':{'front':'front'},'gap_mm':12,'padding_mm':3,
                     'scale_factors':[1,.9,.8,.5],'fill_range':[.45,.65],'target_fill':.55}}
        validate_plan.check_layout_options(p)
        p['layout']['scale_factors']=[1,.5,.75]
        with self.assertRaisesRegex(ValueError,'descending'):validate_plan.check_layout_options(p)
        p['layout']['scale_factors']=[1,.5];p['layout']['target_fill']=.9
        with self.assertRaisesRegex(ValueError,'fill'):validate_plan.check_layout_options(p)

    def test_reported_occupation_is_sum_of_block_and_table_areas(self):
        result=planner.pack_envelopes(self.blocks(),True,[25,65,415,292],table_sizes_mm=[[115,49]])
        boxes=list(result['bounds_mm'].values())+result['table_bounds_mm']
        self.assertAlmostEqual(result['occupied_fraction'],sum((b[2]-b[0])*(b[3]-b[1]) for b in boxes)/(390*227))
        self.assertEqual(len(result['balance_offset_mm']),2)

    def test_reopened_layout_rejects_changed_view_position_or_envelope(self):
        request={'blocks':self.blocks(),'first_angle':True,'usable_bounds_mm':[25,65,415,292],
                 'reserved_boxes_mm':[],'gap_mm':12,'orthographic_views':{'front':'front','top':'top','right':'right'}}
        solved=planner.pack_envelopes(**request);solved['measurement']=request
        solved['actual_bounds_mm']=solved['bounds_mm'];solved['actual_table_bounds_mm']=[]
        plan={'sheet':{'width_mm':420,'height_mm':297},'views':[],
              'layout':{'usable_bounds_mm':[25,65,415,292],'reserved_boxes_mm':[],
                        'orthographic_views':request['orthographic_views'],'gap_mm':12,'padding_mm':2},'line_hierarchy':True}
        snap=[]
        for key in self.blocks():
            pos=solved['positions_mm'][key];b=solved['bounds_mm'][key]
            plan['views'].append({'id':key,'model_view':'*'+key,'position_mm':[1,1],'scale':1})
            snap.append({'view':key,'source':'part.SLDPRT','configuration':'Default','orientation':'*'+key,
                         'position':[pos[0]/1000,pos[1]/1000],'scale':1,'outline':[v/1000 for v in b],
                         'envelope_mm':[b[0]+2,b[1]+2,b[2]-2,b[3]-2],'annotations':[],
                         'line_hierarchy':{'visible_edges':2,'dimension_lines':0,'extension_lines':0}})
        facts={'path':'part.SLDPRT','configuration':'Default'}
        self.assertEqual(verify_outputs.check_native_plan(snap,plan,facts,{},solved)['layout_flags'],[])
        changed=copy.deepcopy(snap);changed[0]['position'][0]+=.01
        with self.assertRaisesRegex(ValueError,'position'):verify_outputs.check_native_plan(changed,plan,facts,{},solved)
        changed=copy.deepcopy(snap);changed[0]['envelope_mm'][2]+=10
        with self.assertRaisesRegex(ValueError,'envelope'):verify_outputs.check_native_plan(changed,plan,facts,{},solved)
        changed=copy.deepcopy(snap);changed[0]['line_hierarchy']['visible_edges']=0
        with self.assertRaisesRegex(ValueError,'hierarchy'):verify_outputs.check_native_plan(changed,plan,facts,{},solved)


if __name__=='__main__':unittest.main()
