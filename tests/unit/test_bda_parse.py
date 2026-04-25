from app.bda.parse import parse_payload


BOL_PAYLOAD = {
    "matched_blueprint": {"name": "bill_of_lading"},
    "document_class": {"type": "Document"},
    "pages": [{"page_index": 0}, {"page_index": 1}],
    "inference_result": {
        "bol_number": "BOL-123",
        "shipper_name": "Acme Co",
        "containers": [{"container_number": "ABCD1234567"}],
    },
    "explainability_info": {
        "bol_number": {"confidence": 0.98},
        "shipper_name": {"confidence": 0.95},
    },
}


def test_parse_bill_of_lading():
    pr = parse_payload(BOL_PAYLOAD)
    assert pr.matched_blueprint == "bill_of_lading"
    assert pr.pages == 2
    assert pr.fields["bol_number"] == "BOL-123"
    assert pr.confidences["bol_number"] == 0.98


def test_unknown_blueprint_falls_back():
    p = {"pages": [{"page_index": 0}], "inference_result": {"foo": "bar"}}
    pr = parse_payload(p)
    assert pr.matched_blueprint == "unknown"
    assert pr.fields == {"foo": "bar"}
    assert pr.pages == 1


def test_field_count_top_level_plus_nested_lists():
    payload = {
        "matched_blueprint": {"name": "commercial_invoice"},
        "pages": [{}],
        "inference_result": {
            "invoice_number": "INV-1",
            "line_items": [
                {"description": "x", "quantity": 1},
                {"description": "y", "quantity": 2},
            ],
        },
    }
    pr = parse_payload(payload)
    assert pr.field_count == 4
