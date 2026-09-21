import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from param_manager import refdata,locking
from param_manager.desktop_documents import DesktopDocuments

class DocumentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.cfg=self.root/'config.json'
        self.cfg.write_text(json.dumps({'save_dir':str(self.root)}))
        self.path=refdata.ip_path(str(self.root));refdata.create_blank_ip(self.path)
        wb=openpyxl.load_workbook(self.path);ws=wb.active
        ws.cell(1,4,'접속ID');ws.cell(1,5,'비밀번호')
        ws.append(['AOI-01','10.0.0.1','Camtek','secret-user','secret-pass'])
        wb.save(self.path);wb.close()
        self.doc=DesktopDocuments(self.cfg);self.catalog=self.doc.open('ip')
        self.patch=patch.object(locking,'VERIFY_DELAY_SEC',0);self.patch.start();self.addCleanup(self.patch.stop)

    def test_credentials_never_exposed(self):
        payload=self.doc.page({'snapshot':self.catalog['snapshot']})
        self.assertEqual(len(payload['rows'][0]['cells']),3)
        self.assertNotIn('secret',json.dumps(payload))

    def test_edit_preserves_other_cells_and_formats(self):
        result=self.doc.edit({'snapshot':self.catalog['snapshot'],'row':0,'column':1,'value':'10.0.0.2','color':'#112233'})
        self.assertNotEqual(result['snapshot'],self.catalog['snapshot'])
        wb=openpyxl.load_workbook(self.path);self.addCleanup(wb.close)
        self.assertEqual(wb.active['B2'].value,'10.0.0.2')
        self.assertEqual(wb.active['E2'].value,'secret-pass')
        self.assertEqual(wb.active['B2'].fill.fgColor.rgb[-6:],'112233')

    def test_stale_path_and_nonlisted_column_rejected(self):
        for bad in ('/etc','unknown'):
            with self.assertRaises(ValueError):self.doc.open(bad)
        self.catalog=self.doc.open('ip')
        with self.assertRaises(ValueError):
            self.doc.edit({'snapshot':self.catalog['snapshot'],'row':0,'column':4,'value':'bad','color':''})
        with open(self.path,'ab') as f:f.write(b'change')
        with self.assertRaises(ValueError):
            self.doc.edit({'snapshot':self.catalog['snapshot'],'row':0,'column':1,'value':'bad','color':''})

    def test_reference_formula_is_text(self):
        path=refdata.ref_path(str(self.root));refdata.create_blank_reference(path)
        cat=self.doc.open('reference')
        self.doc.edit({'snapshot':cat['snapshot'],'row':0,'column':1,'value':'=1+1','color':''})
        wb=openpyxl.load_workbook(path);self.addCleanup(wb.close)
        self.assertEqual(wb.active['B1'].data_type,'s')

    def test_append_preserves_hidden_credentials_and_literal_formula(self):
        result=self.doc.append({'snapshot':self.catalog['snapshot'],'values':['AOI-02','=1+1','Camtek']})
        self.assertEqual(result['total'],2)
        wb=openpyxl.load_workbook(self.path);self.addCleanup(wb.close)
        self.assertEqual(wb.active['E2'].value,'secret-pass')
        self.assertIsNone(wb.active['E3'].value)
        self.assertEqual(wb.active['B3'].value,'=1+1')
        self.assertEqual(wb.active['B3'].data_type,'s')

    def test_append_rejects_invalid_and_stale(self):
        original=Path(self.path).read_bytes()
        for values in ([],['','',''],['x']*4,[True,'',''],['x'*4001,'','']):
            with self.assertRaises(ValueError):
                self.doc.append({'snapshot':self.catalog['snapshot'],'values':values})
        self.assertEqual(Path(self.path).read_bytes(),original)
        with open(self.path,'ab') as f:f.write(b'changed')
        with self.assertRaises(ValueError):
            self.doc.append({'snapshot':self.catalog['snapshot'],'values':['new','','']})

    def test_append_other_lock_keeps_original(self):
        original=Path(self.path).read_bytes()
        locking.acquire(self.path,'another-user')
        self.addCleanup(lambda:locking.release(self.path,'another-user'))
        with self.assertRaises(ValueError):
            self.doc.append({'snapshot':self.catalog['snapshot'],'values':['new','','']})
        self.assertEqual(Path(self.path).read_bytes(),original)

    def test_append_failed_replace_preserves_workbook_and_cleans_temp(self):
        original=Path(self.path).read_bytes()
        with patch('param_manager.desktop_documents.os.replace',side_effect=OSError('blocked')):
            with self.assertRaises(OSError):
                self.doc.append({'snapshot':self.catalog['snapshot'],'values':['new','','']})
        self.assertEqual(Path(self.path).read_bytes(),original)
        self.assertEqual(list(self.root.rglob('.rev1-document-*')),[])

    def test_append_reference_and_missing_header(self):
        path=refdata.ref_path(str(self.root));refdata.create_blank_reference(path)
        cat=self.doc.open('reference')
        result=self.doc.append({'snapshot':cat['snapshot'],'values':['text']*len(cat['headers'])})
        self.assertEqual(result['total'],cat['total']+1)
        wb=openpyxl.load_workbook(self.path);wb.active['B1']='unknown';wb.save(self.path);wb.close()
        cat=self.doc.open('ip')
        with self.assertRaises(ValueError):
            self.doc.append({'snapshot':cat['snapshot'],'values':['new','','']})

if __name__=='__main__':unittest.main()
