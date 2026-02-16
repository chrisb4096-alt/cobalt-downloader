#!/usr/bin/env python3
"""Generate 'Save Video' iOS Shortcut (.shortcut binary plist)
Uses only named variables + implicit input flow (no magic variable UUIDs).
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
    return {"Value": {"string": s}, "WFSerializationType": "WFTextTokenString"}


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
    """Set Variable (uses implicit input from previous action)."""
    return act("setvariable", {"WFVariableName": name})


def getvar(name):
    """Get Variable (loads a named variable into the flow)."""
    return act("getvariable", {"WFVariable": var_ref(name)})


def getkey(key, from_var=None):
    """Get Dictionary Value. Uses implicit input or explicit named variable."""
    params = {"WFDictionaryKey": key}
    if from_var:
        params["WFInput"] = var_ref(from_var)
    return act("getvalueforkey", params)


def build_actions():
    g_input = new_uuid()
    g_error = new_uuid()
    g_picker = new_uuid()

    actions = []

    # --- Input handling ---

    # 1. IF Shortcut Input has any value
    actions.append(act("conditional", {
        "GroupingIdentifier": g_input,
        "WFControlFlowMode": 0,
        "WFCondition": 100,
        "WFInput": shortcut_input(),
    }))

    # 2. Set videoURL = Shortcut Input (explicit reference)
    actions.append(act("setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": shortcut_input(),
    }))

    # 3. Otherwise
    actions.append(act("conditional", {
        "GroupingIdentifier": g_input,
        "WFControlFlowMode": 1,
    }))

    # 4. Get Clipboard → 5. Set videoURL (implicit from clipboard)
    actions.append(act("getclipboard"))
    actions.append(setvar("videoURL"))

    # 6. End If
    actions.append(act("conditional", {
        "GroupingIdentifier": g_input,
        "WFControlFlowMode": 2,
    }))

    # --- API call ---

    # 7. POST to cobalt API
    actions.append(act("downloadurl", {
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

    # 8. Save API response as named variable (implicit from POST)
    actions.append(setvar("apiResponse"))

    # 9. Get "status" from apiResponse → 10. Save as named var
    actions.append(getkey("status", from_var="apiResponse"))
    actions.append(setvar("status"))

    # --- Error check ---

    # 11. IF status contains "error"
    actions.append(act("conditional", {
        "GroupingIdentifier": g_error,
        "WFControlFlowMode": 0,
        "WFCondition": 4,
        "WFConditionalActionString": "error",
        "WFInput": var_ref("status"),
    }))

    # 12. Get "error" from apiResponse → 13. Save → 14. Show Alert
    actions.append(getkey("error", from_var="apiResponse"))
    actions.append(setvar("errorMsg"))
    actions.append(act("alert", {
        "WFAlertActionTitle": "Download Failed",
        "WFAlertActionMessage": var_text("errorMsg"),
    }))

    # 15. Otherwise (success)
    actions.append(act("conditional", {
        "GroupingIdentifier": g_error,
        "WFControlFlowMode": 1,
    }))

    # --- Picker check (Instagram carousels) ---

    # 16. IF status contains "picker"
    actions.append(act("conditional", {
        "GroupingIdentifier": g_picker,
        "WFControlFlowMode": 0,
        "WFCondition": 4,
        "WFConditionalActionString": "picker",
        "WFInput": var_ref("status"),
    }))

    # 17. Get "picker" array → 18. First Item → 19. Get "url" → 20. Save as downloadURL
    actions.append(getkey("picker", from_var="apiResponse"))
    actions.append(act("getitemfromlist", {"WFItemSpecifier": "First Item"}))
    actions.append(getkey("url"))  # implicit from list item
    actions.append(setvar("downloadURL"))

    # 21. Download → 22. Save to Photos → 23. Notify
    actions.append(act("downloadurl", {"WFURL": var_text("downloadURL")}))
    actions.append(act("savetocameraroll"))  # implicit from download
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 24. Otherwise (tunnel/redirect)
    actions.append(act("conditional", {
        "GroupingIdentifier": g_picker,
        "WFControlFlowMode": 1,
    }))

    # 25. Get "url" from apiResponse → 26. Save → 27. Download → 28. Save → 29. Notify
    actions.append(getkey("url", from_var="apiResponse"))
    actions.append(setvar("downloadURL"))
    actions.append(act("downloadurl", {"WFURL": var_text("downloadURL")}))
    actions.append(act("savetocameraroll"))  # implicit from download
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 30. End If (picker)
    actions.append(act("conditional", {
        "GroupingIdentifier": g_picker,
        "WFControlFlowMode": 2,
    }))

    # 31. End If (error)
    actions.append(act("conditional", {
        "GroupingIdentifier": g_error,
        "WFControlFlowMode": 2,
    }))

    return actions


def build_debug_actions():
    """Debug version: shows full API response, copies to clipboard, then downloads."""
    g_input = new_uuid()

    actions = []

    # 1-6: Same input handling
    actions.append(act("conditional", {
        "GroupingIdentifier": g_input, "WFControlFlowMode": 0,
        "WFCondition": 100, "WFInput": shortcut_input(),
    }))
    actions.append(act("setvariable", {
        "WFVariableName": "videoURL", "WFInput": shortcut_input(),
    }))
    actions.append(act("conditional", {
        "GroupingIdentifier": g_input, "WFControlFlowMode": 1,
    }))
    actions.append(act("getclipboard"))
    actions.append(setvar("videoURL"))
    actions.append(act("conditional", {
        "GroupingIdentifier": g_input, "WFControlFlowMode": 2,
    }))

    # 7. API call
    actions.append(act("downloadurl", {
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

    # 8. Save response as named variable (implicit)
    actions.append(setvar("apiResponse"))

    # 9. Load apiResponse → Quick Look (scrollable JSON viewer)
    actions.append(getvar("apiResponse"))
    actions.append(act("previewdocument"))  # implicit from getvar

    # 10. Copy to clipboard
    actions.append(getvar("apiResponse"))
    actions.append(act("setclipboard"))  # implicit from getvar

    # 11. Try download: get "url" from apiResponse → save → download → save
    actions.append(getkey("url", from_var="apiResponse"))
    actions.append(setvar("downloadURL"))
    actions.append(act("downloadurl", {"WFURL": var_text("downloadURL")}))
    actions.append(act("savetocameraroll"))  # implicit
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video (Debug)",
        "WFNotificationActionBody": "Video saved! Response copied to clipboard.",
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
