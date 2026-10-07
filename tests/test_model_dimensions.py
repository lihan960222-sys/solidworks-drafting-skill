import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import validate_plan
import verify_outputs

class ModelDimensionTests(unittest.TestCase):
    def test_same_short_annotation_name_on_different_features_is_scoped_by_dimension(self):
        names=['D1@Sketch1','D1@Sketch2']
        p={'sheet':{'width_mm':420,'height_mm':297},'views':[{'id':'front','model_view':'*Front','position_mm':[100,100],'scale':1}], 'model_dimensions':{'keep':names},'dimension_ids':['model:'+n for n in names]}
        annotations=[{'annotation_name':'D1','name':n,'value_si':.08+i*.01,'position':[.1,.12+i*.02,0]} for i,n in enumerate(names)]
        snap=[{'view':'front','source':'part.SLDPRT','configuration':'Default','orientation':'*Front','position':[.1,.1],'scale':1,'outline':[.05,.05,.15,.15],'annotations':annotations}]
        facts={'path':'part.SLDPRT','configuration':'Default','features':[{'dimensions':[{'name':n+'@Part.Part','value_si':.08+i*.01} for i,n in enumerate(names)]}]}
        bindings={'model:'+a['name']:{'annotation_name':'D1','dimension_name':a['name'],'view':'front','position':a['position']} for a in annotations}
        try:verify_outputs.check_native_plan(snap,p,facts,bindings)
        except ValueError as exc:self.fail('Feature-scoped dimension identity rejected: '+str(exc))

    def test_hidden_feature_option_is_explicit_and_boolean(self):
        try:validate_plan.check_supported({'model_dimensions':{'keep':['D1@Sketch1'],'include_hidden_features':True}})
        except ValueError as exc:self.fail('Explicit hidden-feature import option rejected: '+str(exc))
        with self.assertRaisesRegex(ValueError,'boolean'):
            validate_plan.check_supported({'model_dimensions':{'keep':[],'include_hidden_features':'yes'}})

    def test_selection_is_source_identity_not_arbitrary_dimension_name(self):
        facts={'features':[{'dimensions':[{'name':'D1@Sketch1@Part.Part','value_si':.08}]}]}
        self.assertTrue(callable(getattr(validate_plan,'check_model_dimensions',None)), 'Source identity preflight is missing')
        validate_plan.check_model_dimensions({'model_dimensions':{'keep':['D1@Sketch1']}},facts)
        validate_plan.check_model_dimensions({'model_dimensions':{'keep':['D1@Sketch1@Part.Part']}},facts)
        with self.assertRaisesRegex(ValueError,'source'):
            validate_plan.check_model_dimensions({'model_dimensions':{'keep':['D1@NoSuchFeature']}},facts)
        with self.assertRaisesRegex(ValueError,'same|duplicate|alias'):
            validate_plan.check_model_dimensions({'model_dimensions':{'keep':['D1@Sketch1','D1@Sketch1@Part.Part']}},facts)

    def test_full_source_identity_survives_shortened_native_snapshot(self):
        name='D1@Sketch1@Part.Part'
        p={'sheet':{'width_mm':420,'height_mm':297},'views':[{'id':'front','model_view':'*Front','position_mm':[100,100],'scale':1}], 'model_dimensions':{'keep':[name]},'dimension_ids':['model:'+name]}
        a={'annotation_name':'RD1','name':'D1@Sketch1','value_si':.08,'position':[.1,.12,0]}
        snap=[{'view':'front','source':'part.SLDPRT','configuration':'Default','orientation':'*Front','position':[.1,.1],'scale':1,'outline':[.05,.05,.15,.15],'annotations':[a]}]
        facts={'path':'part.SLDPRT','configuration':'Default','features':[{'dimensions':[{'name':name,'value_si':.08}]}]}
        bindings={'model:'+name:{'annotation_name':'RD1','view':'front','position':[.1,.12,0]}}
        try:verify_outputs.check_native_plan(snap,p,facts,bindings)
        except ValueError as exc:self.fail('Valid full source identity rejected after native snapshot normalization: '+str(exc))
        a['value_si']=.02
        with self.assertRaisesRegex(ValueError,'missing|changed'):
            verify_outputs.check_native_plan(snap,p,facts,bindings)

if __name__=='__main__':unittest.main()
