#!/usr/bin/env python3
"""Generate 'Save Video' iOS Shortcut (.shortcut binary plist)
Uses string WFCondition values + implicit input flow (no WFInput in conditionals).
Format validated against ScPL compiler output and shortcuts-toolkit.
"""
import plistlib
import uuid
import os

API_URL = "https://cobalt-production-97bf.up.railway.app/"
API_KEY = "JacAZJQQjLUsUjjqZCedjJQOJFfqhwYG"
HUBSIGN_URL = "https://hubsign.routinehub.services/sign"


def new_uuid():
    return str(uuid.uuid4()).upper()


def text(s):
    return {
        "Value": {"string": s, "attachmentsByRange": {}},
        "WFSerializationType": "WFTextTokenString",
    }


def var_text(var_name):
    """Text field containing a named variable reference."""
    return {
        "Value": {
            "attachmentsByRange": {
                "{0, 1}": {"Type": "Variable", "VariableName": var_name}
            },
            "string": "\ufffc",
        },
        "WFSerializationType": "WFTextTokenString",
    }


def output_text(action_uuid, output_name):
    """Text field referencing a specific action's output by UUID."""
    return {
        "Value": {
            "attachmentsByRange": {
                "{0, 1}": {
                    "Type": "ActionOutput",
                    "OutputUUID": action_uuid,
                    "OutputName": output_name,
                }
            },
            "string": "\ufffc",
        },
        "WFSerializationType": "WFTextTokenString",
    }


def output_ref(action_uuid, output_name):
    """Direct reference to a specific action's output by UUID."""
    return {
        "Value": {
            "Type": "ActionOutput",
            "OutputUUID": action_uuid,
            "OutputName": output_name,
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def var_ref(var_name):
    """Direct reference to a named variable."""
    return {
        "Value": {"Type": "Variable", "VariableName": var_name},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def shortcut_input():
    return {
        "Value": {"Type": "ExtensionInput"},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def dict_item(key, value, item_type=0):
    return {"WFItemType": item_type, "WFKey": text(key), "WFValue": value}


def dict_value(items):
    return {
        "Value": {"WFDictionaryFieldValueItems": items},
        "WFSerializationType": "WFDictionaryFieldValue",
    }


def act(identifier, params=None):
    return {
        "WFWorkflowActionIdentifier": f"is.workflow.actions.{identifier}",
        "WFWorkflowActionParameters": params or {},
    }


def setvar(name):
    return act("setvariable", {"WFVariableName": name})


def getvar(name):
    return act("getvariable", {"WFVariable": var_ref(name)})


def getkey(key, from_var=None):
    params = {"WFDictionaryKey": key}
    if from_var:
        params["WFInput"] = var_ref(from_var)
    return act("getvalueforkey", params)


def if_begin(group_id, condition, value=None):
    """If block start. Condition is a STRING: 'Contains', 'Equals',
    'Has Any Value', 'Does Not Have Any Value', etc.
    Input comes implicitly from previous action (no WFInput)."""
    params = {
        "GroupingIdentifier": group_id,
        "WFControlFlowMode": 0,
        "WFCondition": condition,
    }
    if value is not None:
        params["WFConditionalActionString"] = value
    return act("conditional", params)


def if_else(group_id):
    return act("conditional", {
        "GroupingIdentifier": group_id,
        "WFControlFlowMode": 1,
    })


def if_end(group_id):
    return act("conditional", {
        "GroupingIdentifier": group_id,
        "WFControlFlowMode": 2,
    })


def build_actions():
    g_input = new_uuid()
    g_error = new_uuid()
    g_picker = new_uuid()

    # UUIDs for actions whose output we reference later
    api_post_uuid = new_uuid()
    picker_geturl_uuid = new_uuid()
    direct_geturl_uuid = new_uuid()

    actions = []

    # --- Input handling ---

    # 1. Set videoURL from Shortcut Input (may be empty if run manually)
    actions.append(act("setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": shortcut_input(),
    }))

    # 2. Load videoURL into implicit flow for the If check
    actions.append(getvar("videoURL"))

    # 3. IF [implicit] does not have any value → get from clipboard
    actions.append(if_begin(g_input, "Does Not Have Any Value"))

    # 4. Get Clipboard → overwrite videoURL
    actions.append(act("getclipboard"))
    actions.append(setvar("videoURL"))

    # 5. End If
    actions.append(if_end(g_input))

    # --- API call ---

    # 6. POST to cobalt API (UUID so we can reference its output)
    actions.append(act("downloadurl", {
        "UUID": api_post_uuid,
        "Advanced": True,
        "ShowHeaders": True,
        "WFURL": API_URL,
        "WFHTTPMethod": "POST",
        "WFHTTPHeaders": dict_value([
            dict_item("Accept", text("application/json")),
            dict_item("Content-Type", text("application/json")),
            dict_item("Authorization", text(f"Api-Key {API_KEY}")),
        ]),
        "WFHTTPBodyType": "JSON",
        "WFJSONValues": dict_value([
            dict_item("url", var_text("videoURL")),
            dict_item("videoQuality", text("max")),
            dict_item("filenameStyle", text("pretty")),
            dict_item("youtubeVideoCodec", text("h264")),
        ]),
    }))

    # 7. Save API response
    actions.append(setvar("apiResponse"))

    # 8-9. Get "status" key → save
    actions.append(getkey("status", from_var="apiResponse"))
    actions.append(setvar("status"))

    # --- Error check ---

    # 10. Load status into flow, then IF contains "error"
    actions.append(getvar("status"))
    actions.append(if_begin(g_error, "Contains", "error"))

    # 11-13. Get error message → save → alert
    actions.append(getkey("error", from_var="apiResponse"))
    actions.append(setvar("errorMsg"))
    actions.append(act("alert", {
        "WFAlertActionTitle": "Download Failed",
        "WFAlertActionMessage": var_text("errorMsg"),
    }))

    # 14. Otherwise (success)
    actions.append(if_else(g_error))

    # --- Picker check (Instagram carousels) ---

    # 15. Load status, IF contains "picker"
    actions.append(getvar("status"))
    actions.append(if_begin(g_picker, "Contains", "picker"))

    # 16-18. Get picker array → first item → get url (with UUID)
    actions.append(getkey("picker", from_var="apiResponse"))
    actions.append(act("getitemfromlist", {"WFItemSpecifier": "First Item"}))
    actions.append(act("getvalueforkey", {
        "UUID": picker_geturl_uuid,
        "WFDictionaryKey": "url",
    }))

    # 19-21. Download using ActionOutput ref → save to photos → notify
    actions.append(act("downloadurl", {
        "WFURL": output_text(picker_geturl_uuid, "Dictionary Value"),
    }))
    actions.append(act("savetocameraroll"))
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 22. Otherwise (tunnel/redirect)
    actions.append(if_else(g_picker))

    # 23. Get url from apiResponse (with UUID)
    actions.append(act("getvalueforkey", {
        "UUID": direct_geturl_uuid,
        "WFDictionaryKey": "url",
        "WFInput": var_ref("apiResponse"),
    }))

    # 24-26. Download using ActionOutput ref → save to photos → notify
    actions.append(act("downloadurl", {
        "WFURL": output_text(direct_geturl_uuid, "Dictionary Value"),
    }))
    actions.append(act("savetocameraroll"))
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 27. End If (picker)
    actions.append(if_end(g_picker))

    # 28. End If (error)
    actions.append(if_end(g_error))

    return actions


def build_debug_actions():
    """Step-by-step diagnostic with alerts after each action.
    Test 1: POST without headers (TVDL-style, will get 401 but proves action works)
    Test 2: POST with headers (full cobalt request)
    """
    actions = []

    # --- Step 1: Get clipboard URL ---
    actions.append(act("getclipboard"))
    actions.append(setvar("videoURL"))

    # --- Test 1: POST without headers (matches TVDL format exactly) ---
    # No Advanced, no ShowHeaders, no WFHTTPBodyType, no WFHTTPHeaders
    actions.append(act("downloadurl", {
        "UUID": new_uuid(),
        "WFURL": API_URL,
        "WFHTTPMethod": "POST",
        "WFJSONValues": dict_value([
            dict_item("url", var_text("videoURL")),
        ]),
    }))
    actions.append(setvar("test1Result"))
    actions.append(getvar("test1Result"))
    actions.append(act("setclipboard"))
    actions.append(act("alert", {
        "WFAlertActionTitle": "Test 1: No headers",
        "WFAlertActionMessage": "POST without headers done. Response copied to clipboard. Check it!",
    }))

    # --- Test 2: POST with Authorization header ---
    actions.append(act("downloadurl", {
        "UUID": new_uuid(),
        "ShowHeaders": True,
        "WFURL": API_URL,
        "WFHTTPMethod": "POST",
        "WFHTTPHeaders": dict_value([
            dict_item("Authorization", text(f"Api-Key {API_KEY}")),
        ]),
        "WFHTTPBodyType": "JSON",
        "WFJSONValues": dict_value([
            dict_item("url", var_text("videoURL")),
            dict_item("videoQuality", text("max")),
            dict_item("filenameStyle", text("pretty")),
            dict_item("youtubeVideoCodec", text("h264")),
        ]),
    }))
    actions.append(setvar("test2Result"))
    actions.append(getvar("test2Result"))
    actions.append(act("previewdocument"))
    actions.append(getvar("test2Result"))
    actions.append(act("setclipboard"))
    actions.append(act("alert", {
        "WFAlertActionTitle": "Test 2: With headers",
        "WFAlertActionMessage": "Full POST done. Response shown and copied.",
    }))

    return actions


def make_shortcut(actions_fn, glyph=59511, color=463140863):
    return {
        "WFWorkflowActions": actions_fn(),
        "WFWorkflowClientVersion": "2612.0.15",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": glyph,
            "WFWorkflowIconStartColor": color,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": [
            "WFURLContentItem",
            "WFStringContentItem",
        ],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": ["ActionExtension", "NCWidget", "WatchKit"],
    }


def sign_shortcut(unsigned_path, signed_path):
    """Sign via RoutineHub HubSign service."""
    import urllib.request
    import urllib.error

    boundary = "----ShortcutBoundary"
    filename = os.path.basename(unsigned_path)

    with open(unsigned_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="shortcut"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        HUBSIGN_URL,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            signed_data = resp.read()
            with open(signed_path, "wb") as f:
                f.write(signed_data)
            is_aea = signed_data[:4] == b"AEA1"
            print(f"  Signed: {signed_path} ({len(signed_data)} bytes, AEA={is_aea})")
            return is_aea
    except urllib.error.URLError as e:
        print(f"  Signing failed: {e}")
        return False


def generate_and_sign(name, actions_fn, color=463140863):
    base = os.path.dirname(os.path.abspath(__file__))
    unsigned = os.path.join(base, f"{name}.shortcut")
    signed = os.path.join(base, f"{name} (Signed).shortcut")

    shortcut = make_shortcut(actions_fn, color=color)
    with open(unsigned, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)
    print(f"Generated: {name}.shortcut ({os.path.getsize(unsigned)} bytes)")
    sign_shortcut(unsigned, signed)


if __name__ == "__main__":
    generate_and_sign("Save Video", build_actions)
    generate_and_sign("Save Video Debug", build_debug_actions, color=4282601983)

    print()
    print("Install on iPhone (open in Safari):")
    print("  Main:  https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20(Signed).shortcut")
    print("  Debug: https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20Debug%20(Signed).shortcut")
