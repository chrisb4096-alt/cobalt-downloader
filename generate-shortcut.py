#!/usr/bin/env python3
"""Generate 'Save Video' iOS Shortcut (.shortcut binary plist)"""
import plistlib
import uuid
import os

API_URL = "https://cobalt-production-97bf.up.railway.app/"
API_KEY = "JacAZJQQjLUsUjjqZCedjJQOJFfqhwYG"


def new_uuid():
    return str(uuid.uuid4()).upper()


def text(s):
    return {"Value": {"string": s}, "WFSerializationType": "WFTextTokenString"}


def var_text(var_name):
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
    return {
        "Value": {"Type": "Variable", "VariableName": var_name},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def output_ref(action_uuid, output_name):
    return {
        "Value": {
            "OutputName": output_name,
            "OutputUUID": action_uuid,
            "Type": "ActionOutput",
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def output_text(action_uuid, output_name):
    return {
        "Value": {
            "attachmentsByRange": {
                "{0, 1}": {
                    "OutputName": output_name,
                    "OutputUUID": action_uuid,
                    "Type": "ActionOutput",
                }
            },
            "string": "\ufffc",
        },
        "WFSerializationType": "WFTextTokenString",
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


def action(identifier, params, action_uuid=None):
    a = {
        "WFWorkflowActionIdentifier": identifier,
        "WFWorkflowActionParameters": params,
    }
    if action_uuid:
        a["UUID"] = action_uuid
    return a


def build_actions():
    # Group IDs for conditional blocks
    g_input = new_uuid()
    g_error = new_uuid()
    g_picker = new_uuid()

    # Action UUIDs for referencing outputs
    u_clipboard = new_uuid()
    u_api = new_uuid()
    u_status = new_uuid()
    u_error = new_uuid()
    u_picker_arr = new_uuid()
    u_first_item = new_uuid()
    u_picker_url = new_uuid()
    u_dl_picker = new_uuid()
    u_get_url = new_uuid()
    u_dl = new_uuid()

    actions = []

    # --- Input handling ---

    # 1. IF Shortcut Input has any value
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_input,
        "WFControlFlowMode": 0,
        "WFCondition": 100,
        "WFInput": shortcut_input(),
    }))

    # 2. Set videoURL = Shortcut Input
    actions.append(action("is.workflow.actions.setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": shortcut_input(),
    }))

    # 3. Otherwise
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_input,
        "WFControlFlowMode": 1,
    }))

    # 4. Get Clipboard
    actions.append(action("is.workflow.actions.getclipboard", {}, u_clipboard))

    # 5. Set videoURL = Clipboard
    actions.append(action("is.workflow.actions.setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": output_ref(u_clipboard, "Clipboard"),
    }))

    # 6. End If
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_input,
        "WFControlFlowMode": 2,
    }))

    # --- API call ---

    # 7. POST to cobalt API
    actions.append(action("is.workflow.actions.downloadurl", {
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
    }, u_api))

    # 8. Get "status" from response
    actions.append(action("is.workflow.actions.getvalueforkey", {
        "WFDictionaryKey": "status",
        "WFInput": output_ref(u_api, "Contents of URL"),
    }, u_status))

    # --- Error handling ---

    # 9. IF status contains "error"
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_error,
        "WFControlFlowMode": 0,
        "WFCondition": 4,
        "WFConditionalActionString": "error",
        "WFInput": output_ref(u_status, "Dictionary Value"),
    }))

    # 10. Get "error" from response
    actions.append(action("is.workflow.actions.getvalueforkey", {
        "WFDictionaryKey": "error",
        "WFInput": output_ref(u_api, "Contents of URL"),
    }, u_error))

    # 11. Show Alert with error
    actions.append(action("is.workflow.actions.alert", {
        "WFAlertActionTitle": "Download Failed",
        "WFAlertActionMessage": output_text(u_error, "Dictionary Value"),
    }))

    # 12. Otherwise (success)
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_error,
        "WFControlFlowMode": 1,
    }))

    # --- Picker handling (Instagram carousels, etc.) ---

    # 13. IF status contains "picker"
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_picker,
        "WFControlFlowMode": 0,
        "WFCondition": 4,
        "WFConditionalActionString": "picker",
        "WFInput": output_ref(u_status, "Dictionary Value"),
    }))

    # 14. Get "picker" array from response
    actions.append(action("is.workflow.actions.getvalueforkey", {
        "WFDictionaryKey": "picker",
        "WFInput": output_ref(u_api, "Contents of URL"),
    }, u_picker_arr))

    # 15. Get First Item
    actions.append(action("is.workflow.actions.getitemfromlist", {
        "WFItemSpecifier": "First Item",
        "WFInput": output_ref(u_picker_arr, "Dictionary Value"),
    }, u_first_item))

    # 16. Get "url" from first picker item
    actions.append(action("is.workflow.actions.getvalueforkey", {
        "WFDictionaryKey": "url",
        "WFInput": output_ref(u_first_item, "Item from List"),
    }, u_picker_url))

    # 17. Download picker video
    actions.append(action("is.workflow.actions.downloadurl", {
        "WFURL": output_text(u_picker_url, "Dictionary Value"),
    }, u_dl_picker))

    # 18. Save to Photos
    actions.append(action("is.workflow.actions.savetocameraroll", {
        "WFInput": output_ref(u_dl_picker, "Contents of URL"),
    }))

    # 19. Notification
    actions.append(action("is.workflow.actions.notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 20. Otherwise (tunnel/redirect)
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_picker,
        "WFControlFlowMode": 1,
    }))

    # 21. Get "url" from response
    actions.append(action("is.workflow.actions.getvalueforkey", {
        "WFDictionaryKey": "url",
        "WFInput": output_ref(u_api, "Contents of URL"),
    }, u_get_url))

    # 22. Download video
    actions.append(action("is.workflow.actions.downloadurl", {
        "WFURL": output_text(u_get_url, "Dictionary Value"),
    }, u_dl))

    # 23. Save to Photos
    actions.append(action("is.workflow.actions.savetocameraroll", {
        "WFInput": output_ref(u_dl, "Contents of URL"),
    }))

    # 24. Notification
    actions.append(action("is.workflow.actions.notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 25. End If (picker)
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_picker,
        "WFControlFlowMode": 2,
    }))

    # 26. End If (error)
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_error,
        "WFControlFlowMode": 2,
    }))

    return actions


def create_shortcut():
    return {
        "WFWorkflowActions": build_actions(),
        "WFWorkflowClientVersion": "2612.0.15",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": 59511,
            "WFWorkflowIconStartColor": 463140863,
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


def build_debug_actions():
    """Debug version: shows full API response before downloading."""
    g_input = new_uuid()
    u_clipboard = new_uuid()
    u_api = new_uuid()
    u_response_text = new_uuid()
    u_get_url = new_uuid()
    u_dl = new_uuid()

    actions = []

    # 1-6: Same input handling
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_input, "WFControlFlowMode": 0,
        "WFCondition": 100, "WFInput": shortcut_input(),
    }))
    actions.append(action("is.workflow.actions.setvariable", {
        "WFVariableName": "videoURL", "WFInput": shortcut_input(),
    }))
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_input, "WFControlFlowMode": 1,
    }))
    actions.append(action("is.workflow.actions.getclipboard", {}, u_clipboard))
    actions.append(action("is.workflow.actions.setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": output_ref(u_clipboard, "Clipboard"),
    }))
    actions.append(action("is.workflow.actions.conditional", {
        "GroupingIdentifier": g_input, "WFControlFlowMode": 2,
    }))

    # 7. API call
    actions.append(action("is.workflow.actions.downloadurl", {
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
    }, u_api))

    # 8. Set variable to preserve response
    actions.append(action("is.workflow.actions.setvariable", {
        "WFVariableName": "apiResponse",
        "WFInput": output_ref(u_api, "Contents of URL"),
    }))

    # 9. Convert response to text for display
    actions.append(action("is.workflow.actions.detect.text", {
        "WFInput": output_ref(u_api, "Contents of URL"),
    }, u_response_text))

    # 10. Show full response in Quick Look (scrollable)
    actions.append(action("is.workflow.actions.previewdocument", {
        "WFInput": output_ref(u_response_text, "Text"),
    }))

    # 11. Copy response to clipboard for easy sharing
    actions.append(action("is.workflow.actions.setclipboard", {
        "WFInput": output_ref(u_response_text, "Text"),
    }))

    # 12. Try to download anyway - get "url" from response
    actions.append(action("is.workflow.actions.getvalueforkey", {
        "WFDictionaryKey": "url",
        "WFInput": var_ref("apiResponse"),
    }, u_get_url))

    # 13. Download video
    actions.append(action("is.workflow.actions.downloadurl", {
        "WFURL": output_text(u_get_url, "Dictionary Value"),
    }, u_dl))

    # 14. Save to Photos
    actions.append(action("is.workflow.actions.savetocameraroll", {
        "WFInput": output_ref(u_dl, "Contents of URL"),
    }))

    # 15. Notification
    actions.append(action("is.workflow.actions.notification", {
        "WFNotificationActionTitle": "Save Video (Debug)",
        "WFNotificationActionBody": "Video saved! Response was copied to clipboard.",
    }))

    return actions


def create_debug_shortcut():
    return {
        "WFWorkflowActions": build_debug_actions(),
        "WFWorkflowClientVersion": "2612.0.15",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": 59511,
            "WFWorkflowIconStartColor": 4282601983,  # orange for debug
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


HUBSIGN_URL = "https://hubsign.routinehub.services/sign"


def sign_shortcut(unsigned_path, signed_path):
    """Sign a .shortcut file via RoutineHub HubSign service."""
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
            is_signed = signed_data[:4] == b"AEA1"
            print(f"  Signed: {signed_path} ({len(signed_data)} bytes, AEA={is_signed})")
            return is_signed
    except urllib.error.URLError as e:
        print(f"  Signing failed: {e}")
        return False


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))

    # Main shortcut
    shortcut = create_shortcut()
    unsigned = os.path.join(base, "Save Video.shortcut")
    with open(unsigned, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)
    print(f"Generated: {unsigned} ({os.path.getsize(unsigned)} bytes)")

    signed = os.path.join(base, "Save Video (Signed).shortcut")
    sign_shortcut(unsigned, signed)

    # Debug shortcut
    debug = create_debug_shortcut()
    unsigned_dbg = os.path.join(base, "Save Video (Debug).shortcut")
    with open(unsigned_dbg, "wb") as f:
        plistlib.dump(debug, f, fmt=plistlib.FMT_BINARY)
    print(f"Generated: {unsigned_dbg} ({os.path.getsize(unsigned_dbg)} bytes)")

    signed_dbg = os.path.join(base, "Save Video Debug (Signed).shortcut")
    sign_shortcut(unsigned_dbg, signed_dbg)

    print()
    print("Install on iPhone (open these links in Safari):")
    print("  Main:  https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20(Signed).shortcut")
    print("  Debug: https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20Debug%20(Signed).shortcut")
