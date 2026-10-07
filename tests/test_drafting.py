import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import planner
import validate_plan
import verify_outputs

class DraftingTests(unittest.TestCase):
    def test_projection_and_uniform_scale(self):
        sizes = {'front': [80, 40], 'top': [80, 50], 'right': [50, 40]}
        for first in (True, False):
            result = planner.candidate_layouts(sizes, first_angle=first, annotation_margin_mm=15)
            self.assertTrue(result)
            p = result[0]['positions_mm']
            self.assertGreater(p['front'][1] - p['top'][1] if first else p['top'][1] - p['front'][1], 0)
            self.assertGreater(p['front'][0] - p['right'][0] if first else p['right'][0] - p['front'][0], 0)
            self.assertIn(result[0]['paper'], ('A4', 'A3', 'A2'))
            for box in result[0]['reserved_bounds_mm'].values():
                self.assertFalse(planner.overlaps(box, result[0]['title_block_mm']))

    def test_a2_overflow_is_failure_not_smaller_text(self):
        self.assertEqual(planner.candidate_layouts({'front':[100000,100000]}, False, 15), [])

    def test_no_png_or_extra_deliverables(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            for name in ('part.dwg', 'part.pdf'):
                (p/name).write_bytes(b'x')
            self.assertEqual(verify_outputs.delivery_files(p), ['part.dwg', 'part.pdf'])
            (p/'preview.png').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError, 'deliverable'):
                verify_outputs.delivery_files(p)

    def test_coverage_requires_all_geometry_not_dimension_count(self):
        facts = {'draft_features':[{'id':'hole', 'required':['diameter','depth']}]}
        plan = {'coverage':[{'feature':'hole','status':'covered','fields':{'diameter':{'value':10,'unit':'mm','evidence':'edge:1','annotation':'d1'}}}], 'dimension_ids':['d1']}
        with self.assertRaisesRegex(ValueError, 'depth'):
            validate_plan.check_coverage(plan, facts)
        plan['coverage'][0]['fields']['depth'] = {'value':20,'unit':'mm','evidence':'feature:hole','annotation':'d1'}
        self.assertTrue(validate_plan.check_coverage(plan, facts)['complete'])

    def test_empty_feature_inventory_never_certifies_completeness(self):
        with self.assertRaisesRegex(ValueError,'Empty'):
            validate_plan.check_coverage({'coverage':[],'dimension_ids':[]},{'draft_features':[]})

    def test_table_identity_and_coordinate_frame(self):
        table = {'role':'nominal_hole_schedule','feature_ids':['H1'], 'units':'mm', 'origin':[0,0,0],'axes':['X','Y'], 'rows':[['ID','D'],['H1','10']], 'row_evidence':['edge:1']}
        validate_plan.check_table(table)
        for key in ('origin','units','row_evidence'):
            bad=copy.deepcopy(table); del bad[key]
            with self.assertRaises(ValueError):validate_plan.check_table(bad)
        bad=copy.deepcopy(table); bad['feature_ids']=['H1','H1']
        with self.assertRaises(ValueError):validate_plan.check_table(bad)

    def test_same_number_different_entity_not_duplicate(self):
        items=[{'entity':'a','meaning':'diameter','value':10},{'entity':'b','meaning':'diameter','value':10},{'entity':'a','meaning':'diameter','value':10}]
        self.assertEqual(len(planner.unique_definitions(items)),2)

    def test_failures_and_unreviewed_outputs_never_verified(self):
        self.assertEqual(verify_outputs.final_status(False, True, True), 'FAILED')
        self.assertEqual(verify_outputs.final_status(True, True, False), 'REVIEW_REQUIRED')
        self.assertEqual(verify_outputs.final_status(True, True, True), 'DRAFT_VERIFIED')

    def test_readback_scale_and_position_changes_fail(self):
        native=[{'scale':1,'annotations':[{'value_si':.08,'position':[.16,.252,0]}]}]
        quarter=[{'annotations':[{'value_si':.02,'position':[.055,.0685,0]}]}]
        with self.assertRaisesRegex(ValueError,'scale|position'):
            verify_outputs.check_readback(native,quarter)
        correct=[{'annotations':[{'value_si':.08,'position':[.16,.252,0]}]}]
        self.assertTrue(verify_outputs.check_readback(native,correct)['dimensions_checked'])

    def test_dense_plate_uses_side_table_and_fills_a4(self):
        results=planner.candidate_layouts({'front':[80,50],'top':[80,20],'right':[20,50]},True,8,[70,49])
        best=results[0]
        self.assertEqual(best['sheet_mm'],[297,210])
        self.assertGreater(best['scale'],1)
        self.assertEqual(best['table_placement'],'side')
        table=best['table_bounds_mm']
        self.assertTrue(all(not planner.overlaps(table,box) for box in best['reserved_bounds_mm'].values()))

    def test_original_template_regions_remain_reserved(self):
        reserved=[[235,5,415,60],[25,280,85,292]]
        best=planner.candidate_layouts({'front':[80,50],'top':[80,20],'right':[20,50]},True,8,[115,49],fixed_sheet_mm=[420,297],usable_bounds_mm=[25,65,415,292],reserved_boxes_mm=reserved)[0]
        self.assertEqual(best['sheet_mm'],[420,297])
        self.assertEqual(best['scale'],2)
        for box in list(best['reserved_bounds_mm'].values())+[best['table_bounds_mm']]:
            self.assertTrue(all(not planner.overlaps(box,r) for r in reserved))

    def test_visual_review_is_bound_to_both_output_files(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder); (p/'x.dwg').write_bytes(b'AC1032'); (p/'x.pdf').write_bytes(b'pdf')
            review={'dwg_sha256':verify_outputs.sha256(p/'x.dwg'),'pdf_sha256':verify_outputs.sha256(p/'x.pdf'),'checks':{k:True for k in ('template','views','dimensions','symbols','tables','legibility','projection')}}
            self.assertTrue(verify_outputs.check_visual_review(review,p/'x.dwg',p/'x.pdf'))
            (p/'x.dwg').write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_outputs.check_visual_review(review,p/'x.dwg',p/'x.pdf')

    def test_unimplemented_operations_and_mixed_ortho_scales_rejected(self):
        with self.assertRaisesRegex(ValueError,'detail'):
            validate_plan.check_supported({'details':[{'id':'D'}]})
        with self.assertRaisesRegex(ValueError,'scale'):
            validate_plan.check_supported({'views':[{'model_view':'*Front','scale':1},{'model_view':'*Top','scale':2}]})
        validate_plan.check_supported({'views':[{'model_view':'*Front','scale':2},{'model_view':'*Isometric','scale':1}]})

    def test_existing_native_snapshot_cannot_certify_wrong_dimensions(self):
        p={'views':[],'sections':[],'dimensions':[{'expected_mm':80}],'diameters':[],'notes':[],'labels':[],'tables':[]}
        with self.assertRaisesRegex(ValueError,'dimension'):
            verify_outputs.check_native_plan([{'source':'','annotations':[{'value_si':.02}]}],p,{})
        verify_outputs.check_native_plan([{'source':'','annotations':[{'value_si':.08}]}],p,{})

    def test_model_dimension_placement_requires_retained_identity(self):
        with self.assertRaisesRegex(ValueError,'retained'):
            validate_plan.check_supported({'model_dimensions':{'keep':['D1'],'positions':[{'name':'D2','position_mm':[10,20]}]}})

    def test_hole_table_values_match_actual_circle(self):
        table={'role':'nominal_hole_schedule','feature_ids':['H1'],'rows':[['ID','X (mm)','Y (mm)','D (mm)','Depth','Qty'],['H1','20','30','10','20','1']],'row_evidence':['edges:1'],'origin':[0,0,0],'axes':['X','Y'],'units':'mm'}
        facts={'edges':[{'id':1,'type':'circle','body':1,'parameters_si':[.02,.03,.02,0,0,1,.005]}],'faces':[{'body':1,'type':'cylinder','parameters_si':[.02,.03,0,0,0,1,.005],'bounds_si':[.015,.025,0,.025,.035,.02]}],'bodies':[{'id':1,'bounds_si':[0,0,0,.05,.05,.02]}]}
        labels=[{'text':'H1','edge_id':1}]
        validate_plan.check_hole_geometry(table,facts,labels)
        table['rows'][1][3]='8'
        with self.assertRaisesRegex(ValueError,'diameter'):
            validate_plan.check_hole_geometry(table,facts,labels)

    def test_supplemental_missing_geometry_is_not_ignored(self):
        facts={'draft_features':[{'id':'body','required':['depth']}]}
        plan={'dimension_ids':['d'],'coverage':[{'feature':'body','status':'covered','fields':{'depth':{'value':20,'unit':'mm','evidence':'edge:1','annotation':'d'}}},{'feature':'blind-hole','status':'missing_geometry_definition','reason':'no depth'}]}
        with self.assertRaisesRegex(ValueError,'Unknown|supplemental'):
            validate_plan.check_coverage(plan,facts)

    def test_upstream_failure_cannot_be_promoted(self):
        for status,code in [('FAILED',0),('UNKNOWN',0),('NATIVE_REOPEN_VERIFIED',1)]:
            with self.assertRaises(ValueError):verify_outputs.check_upstream({'status':status,'export':{'viewer_exit_code':code}},True)

    def test_experimental_payloads_fail_before_native_mutation(self):
        p={'sheet':{'width_mm':420,'height_mm':297},'views':[{'id':'front','model_view':'*Front','scale':1}], 'linear':[{'id':'x','view':'none','a_edge':999,'b_edge':998,'direction':'diagonal','expected_mm':-1,'position_mm':[-20,0],'evidence':'none'}]}
        with self.assertRaises(ValueError):validate_plan.check_experimental(p,{'edges':[]})

    def test_native_view_orientation_and_position_are_required(self):
        p={'sheet':{'width_mm':420,'height_mm':297},'views':[{'id':'front','model_view':'*Front','position_mm':[100,100],'scale':1}],'sections':[],'dimensions':[],'diameters':[],'notes':[],'labels':[],'tables':[]}
        facts={'path':'source.SLDPRT','configuration':'Default'}
        snapshot=[{'view':'front','source':'source.SLDPRT','configuration':'Default','orientation':'*Top','position':[.1,.1],'scale':1,'outline':[.05,.05,.15,.15],'annotations':[]}]
        with self.assertRaisesRegex(ValueError,'orientation'):verify_outputs.check_native_plan(snapshot,p,facts)
        snapshot[0]['orientation']='*Front';snapshot[0]['position']=[-.1,-.1]
        with self.assertRaisesRegex(ValueError,'position'):verify_outputs.check_native_plan(snapshot,p,facts)

if __name__=='__main__':unittest.main()
