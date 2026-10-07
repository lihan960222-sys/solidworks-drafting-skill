import copy
import sys
import unittest
import json
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import validate_plan
import verify_outputs
import validate_native

class GeometryAuditTests(unittest.TestCase):
    def test_native_plan_validator_accepts_geometry_audit_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);facts=root/'facts.json';template=root/'approved.drwdot';template.write_bytes(b'template')
            facts.write_text(json.dumps({'schema_version':2,'document_type':'part','sha256':'0'*64,'model_views':['*Front'],'edges':[]}),encoding='utf-8')
            p={'version':2,'facts':str(facts),'template':str(template),'output_drawing':str(root/'internal/part.SLDDRW'),'output_pdf':str(root/'deliverables/part.pdf'),'sheet':{'width_mm':420,'height_mm':297,'first_angle':True},'views':[{'id':'front','model_view':'*Front','position_mm':[100,100],'scale':1,'reason':'Nominal profile'}], 'dimensions':[],'sections':[],'labels':[],'tables':[],'notes':[],'unresolved':[],'geometry_audit':{'scope':'nominal_geometry'}}
            try:validate_native.validate(p)
            except ValueError as exc:self.fail('Native validator rejected geometry audit metadata: '+str(exc))

    def fixture(self):
        defs=[{'id':n,'entity':'block','property':n,'frame':'part','annotation':n,'evidence':'faces:'+n} for n in ('length','width','height')]
        checks={k:{'passed':True,'evidence':'Explicit feature reconstruction reviewed'} for k in ('feature_inventory','sizes','locations','orientations','depths_and_sections','patterns_and_relations','dimension_chains','nonredundancy','reconstruction')}
        return {'dimension_ids':['length','width','height'],'geometry_audit':{'source_sha256':'abc','scope':'nominal_geometry','checks':checks,'definitions':defs,'missing_definitions':[],'redundant_definitions':[]}}, {'sha256':'abc'}

    def audit(self,p,f):
        self.assertTrue(callable(getattr(validate_plan,'check_geometry_audit',None)),'Geometry completeness/redundancy gate missing')
        return validate_plan.check_geometry_audit(p,f)

    def test_import_count_without_geometry_audit_cannot_pass(self):
        p,f=self.fixture();del p['geometry_audit']
        with self.assertRaisesRegex(ValueError,'audit'):self.audit(p,f)

    def test_same_value_different_features_are_not_duplicates(self):
        p,f=self.fixture();p['geometry_audit']['definitions'] += [{'id':'hole1','entity':'H1','property':'diameter','frame':'part','annotation':'hole1','evidence':'edges:1'},{'id':'hole2','entity':'H2','property':'diameter','frame':'part','annotation':'hole2','evidence':'edges:2'}];p['dimension_ids']+=['hole1','hole2']
        self.assertEqual(self.audit(p,f)['status'],'PASS')

    def test_same_geometry_property_has_one_driving_definition(self):
        p,f=self.fixture();d=copy.deepcopy(p['geometry_audit']['definitions'][0]);d.update(id='duplicate',annotation='duplicate');p['geometry_audit']['definitions'].append(d);p['dimension_ids'].append('duplicate')
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.audit(p,f)

    def test_missing_hole_depth_or_unknown_location_stops_acceptance(self):
        p,f=self.fixture();p['geometry_audit']['missing_definitions']=['H1 blind depth']
        with self.assertRaisesRegex(ValueError,'Incomplete'):self.audit(p,f)
        p['geometry_audit']['missing_definitions']=[];p['geometry_audit']['checks']['locations']['passed']=False
        with self.assertRaisesRegex(ValueError,'locations'):self.audit(p,f)

    def test_dimension_chain_can_derive_omitted_segment_without_extra_annotation(self):
        p,f=self.fixture();p['geometry_audit']['definitions'].append({'id':'remaining_segment','entity':'step3','property':'length','frame':'part','depends_on':['length','width','height'],'equation':'remaining_segment = length - width - height','evidence':'faces:step3'})
        self.assertEqual(self.audit(p,f)['status'],'PASS')
        p['geometry_audit']['definitions'][-1]['depends_on']=['remaining_segment']
        with self.assertRaisesRegex(ValueError,'cycle'):self.audit(p,f)

    def test_stale_source_unmapped_dimension_or_unsubstantiated_check_fails(self):
        p,f=self.fixture();p['geometry_audit']['source_sha256']='stale'
        with self.assertRaisesRegex(ValueError,'source'):self.audit(p,f)
        p,f=self.fixture();p['dimensions']=[{'id':'extra'}];p['dimension_ids'].append('extra')
        with self.assertRaisesRegex(ValueError,'Unmapped'):self.audit(p,f)
        p,f=self.fixture();p['geometry_audit']['checks']['reconstruction']['evidence']=''
        with self.assertRaisesRegex(ValueError,'reconstruction'):self.audit(p,f)

    def test_native_acceptance_calls_geometry_audit_after_numeric_coverage(self):
        p,f=self.fixture();del p['geometry_audit'];f['path']='part.SLDPRT'
        r={'status':'NATIVE_VERIFIED_REVIEW_REQUIRED','native_worker_exit_code':0,'reopen':{'status':'PASS'}}
        with tempfile.TemporaryDirectory() as folder:
            facts=Path(folder)/'facts.json';facts.write_text(json.dumps(f),encoding='utf-8');p['facts']=str(facts)
            with patch.object(validate_plan,'validate'),patch.object(validate_plan,'check_coverage',return_value={'complete':True}),patch.object(verify_outputs,'check_native_plan',return_value={'layout_flags':[]}),patch.object(verify_outputs,'sha256',return_value='abc'):
                with self.assertRaisesRegex(ValueError,'audit'):verify_outputs.verify_native(p,r)
