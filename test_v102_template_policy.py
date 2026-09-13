import zipfile
import xml.etree.ElementTree as ET

def _sheet_names(path):
    with zipfile.ZipFile(path) as z:
        root=ET.fromstring(z.read("xl/workbook.xml"))
    ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return [x.attrib["name"] for x in root.findall(".//m:sheets/m:sheet",ns)]

def test_download_template_has_only_two_user_sheets():
    assert _sheet_names("Water_Risk_Input_Template.xlsx")==["采购数据","填写说明"]

def test_static_template_matches_policy():
    assert _sheet_names("static/Water_Risk_Input_Template.xlsx")==["采购数据","填写说明"]
