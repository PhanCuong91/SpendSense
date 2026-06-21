from dateutil.zoneinfo import tzfile
import datetime
from app.core.timezone import SGT
from app.parsing.parser import parse_email, extract_plain_text


'''
test scenarios:
No  | Account | Type  | Status
------------------------------- 
1 |Trust   | Spend | Pass (inferred sender: Trust, inferred receiver: Other)
2 |PayLah  | Spend | Pass (inferred sender: PayLah, inferred receiver: Other)
3 |DBS     | Earn  | Pass (inferred sender: Other, inferred receiver: DBS)
4 |DBS → PayLah | Internal Transfer | Pass (inferred sender: DBS, inferred receiver: PayLah)
5 |ACB Online | Spend | Pass (inferred sender: ACB Online, inferred receiver: Other)
6 |DBS -> Trust | Internal Transfer | Pass (inferred sender: DBS, inferred receiver: Other)
7 |DBS -> Trust | Internal Transfer | Pass (inferred sender: Other, inferred receiver: Trust)
8 |DBS -> ACB | Internal Transfer | Pass (inferred sender: DBS, inferred receiver: Other)
9 |DBS -> ACB | Internal Transfer | Pass (inferred sender: Other, inferred receiver: ACB)
10 | ACB online -> ACB | Internal Transfer | Not done (inferred sender: ACB Online, inferred receiver: Other)
11 | ACB online -> ACB | Internal Transfer | Not done (inferred sender: Other, inferred receiver: ACB)
12 | ACB | earn| Not done (inferred sender: Other, inferred receiver: ACB)
13 | ACB | spend| Not done (inferred sender: ACB, inferred receiver: Other)
14 | ACB Online | earn| Not done (inferred sender: Other, inferred receiver: ACB Online)
15 | DBS | spend| Not done (inferred sender: DBS, inferred receiver: Other)
'''

def test_1_parse_spend_Trust():
    with open('tests/test_parser/test_1_parse_spend_Trust.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    # print(plain_text)
    print("\n\nExtracted Data:")
    with open('tests/test_parser/test_1_parse_spend_Trust.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 3.64
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "Trust"   # Trust alias
    assert extracted["inferred_receiver"] == "Other"   # DBS alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "spend"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 4, 0, 0, tzinfo=SGT)   # Trust alias

def test_2_parse_spend_Paylah():
    with open('tests/test_parser/test_2_parse_spend_Paylah.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    print(plain_text)
    with open('tests/test_parser/test_2_parse_spend_Paylah.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 8.8
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "PayLah"   # PayLah alias
    assert extracted["inferred_receiver"] == "Other"   # DBS alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "spend"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 4, 0, 0, tzinfo=SGT)

def test_3_parse_earn_DBS():
    with open('tests/test_parser/test_3_parse_earn_DBS.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    # print(plain_text)
    with open('tests/test_parser/test_3_parse_earn_DBS.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 2.25
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "Other"   # DBS alias
    assert extracted["inferred_receiver"] == "DBS"   # DBS alias
    assert extracted["debit_credit"] == "credit"
    assert extracted["type_info"] == "earn"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 4, 0, 0, tzinfo=SGT)   # DBS alias

def test_4_parse_internal_transfer_DBS_Paylah():
    with open('tests/test_parser/test_4_parse_internal_transfer_DBS_Paylah.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    with open('tests/test_parser/test_4_parse_internal_transfer_DBS_Paylah.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    sample_subject = "asdas"
    print(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 100.0
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "DBS"   # DBS alias
    assert extracted["inferred_receiver"] == "PayLah"   # PayLah alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 4, 0, 0, tzinfo=SGT)   # DBS alias

def test_5_parse_spend_ACB_Online():
    with open('tests/test_parser/test_5_parse_spend_ACB_Online.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    with open('tests/test_parser/test_5_parse_spend_ACB_Online.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 6000000.0
    assert extracted["currency"] == "VND"
    assert extracted["sign"] == "-"   # ACB Online alias
    assert extracted["inferred_sender"] == "ACB Online"   # ACB Online alias
    assert extracted["inferred_receiver"] == "Other"   # DBS alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3,  5, 0, 0, tzinfo=SGT)   # ACB Online alias

def test_5_1_parse_spend_ACB_Online():
    with open('tests/test_parser/decoded_email_19cbddb7083f3187.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    with open('tests/test_parser/decoded_email_19cbddb7083f3187.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 4000000.0
    assert extracted["currency"] == "VND"
    assert extracted["sign"] == "-"   # ACB Online alias
    assert extracted["inferred_sender"] == "ACB Online"   # ACB Online alias
    assert extracted["inferred_receiver"] == "Other"   # DBS alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3,  5, 0, 0, tzinfo=SGT) 

def test_6_parse_internal_transfer_DBS_Trust():
    with open('tests/test_parser/test_6_parse_internal_transfer_DBS_Trust.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    # print(plain_text)
    with open('tests/test_parser/test_6_parse_internal_transfer_DBS_Trust.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 10.0
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "DBS"   # DBS alias
    assert extracted["inferred_receiver"] == "Trust"   # Trust alias
    assert extracted["debit_credit"] == "credit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 8, 0, 0, tzinfo=SGT)   # DBS alias

def test_7_parse_internal_transfer_DBS_Trust():
    with open('tests/test_parser/test_7_parse_internal_transfer_DBS_Trust.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    # print(plain_text)
    with open('tests/test_parser/test_7_parse_internal_transfer_DBS_Trust.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 10.0
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "DBS"   # DBS alias
    assert extracted["inferred_receiver"] == "Trust"   # Trust alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 8, 0, 0, tzinfo=SGT)   # DBS alias

def test_8_parse_internal_transfer_DBS_ACB():
    with open('tests/test_parser/test_8_parse_internal_transfer_DBS_ACB.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    with open('tests/test_parser/test_8_parse_internal_transfer_DBS_ACB.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    sample_subject = "asdas"
    # print(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 5003.00
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "DBS"   # DBS alias
    assert extracted["inferred_receiver"] == "ACB Online"   # ACB Online alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 2, 0, 0, tzinfo=SGT)   # DBS alias

def test_9_parse_internal_transfer_DBS_ACB():
    with open('tests/test_parser/test_9_parse_internal_transfer_DBS_ACB.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    # print(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 101341000.0
    assert extracted["currency"] == "VND"
    assert extracted["inferred_sender"] == "DBS"   # DBS alias
    assert extracted["inferred_receiver"] == "ACB Online"   # ACB Online alias
    assert extracted["debit_credit"] == "credit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 2, 0, 0, tzinfo=SGT)   # DBS alias
def test_10_parse_internal_transfer_ACB_Online_ACB():
    with open('tests/test_parser/test_10_parse_internal_transfer_ACB_Online_ACB.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    with open('tests/test_parser/test_10_parse_internal_transfer_ACB_Online_ACB.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 200000.0
    assert extracted["currency"] == "VND"
    assert extracted["inferred_sender"] == "ACB Online"   # ACB Online alias
    assert extracted["inferred_receiver"] == "Other"   # ACB alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 8, 0, 0, tzinfo=SGT)   # ACB Online alias

def test_11_parse_internal_transfer_ACB_Online_ACB():
    with open('tests/test_parser/test_11_parse_internal_transfer_ACB_Online_ACB.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    with open('tests/test_parser/test_11_parse_internal_transfer_ACB_Online_ACB.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 200000.0
    assert extracted["currency"] == "VND"
    assert extracted["inferred_sender"] == "Other"   # ACB Online alias
    assert extracted["inferred_receiver"] == "ACB"   # ACB alias
    assert extracted["debit_credit"] == "credit"
    assert extracted["type_info"] == "InternalTransfer"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 8, 0, 0, tzinfo=SGT)   # ACB Online alias

def test_15_parse_internal_transfer_DBS():
    with open('tests/test_parser/test_15_parse_internal_transfer_DBS.json', encoding="utf-8") as f:
        html = f.read()
    plain_text = extract_plain_text(html)
    sample_subject = "asdas"
    with open('tests/test_parser/test_15_parse_internal_transfer_DBS.txt', 'w', encoding='utf-8') as out_f:
        out_f.write(plain_text)
    print("\n\nExtracted Data:")
    extracted = parse_email(sample_subject, plain_text)

    assert extracted["amount"] == 30.0
    assert extracted["currency"] == "SGD"
    assert extracted["inferred_sender"] == "DBS"   # DBS alias
    assert extracted["inferred_receiver"] == "Other"   # Other alias
    assert extracted["debit_credit"] == "debit"
    assert extracted["type_info"] == "spend"
    assert extracted["datetime_sgt"] == datetime.datetime(2026, 3, 13, 0, 0, tzinfo=SGT)   # DBS alias


