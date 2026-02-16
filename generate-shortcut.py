#!/usr/bin/env python3
"""Generate 'Save Video' iOS Shortcut (.shortcut binary plist)
Format reverse-engineered from working iOS-built shortcut (Feb 2026).
Key patterns: WFHTTPBodyType JSON + WFJSONValues, explicit WFInput ActionOutput
refs with UUIDs, WFCoercionVariableAggrandizement for URL type coercion.
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
    return {
        "Value": {
            "string": "\ufffc",
            "attachmentsByRange": {
                "{0, 1}": {"Type": "Variable", "VariableName": var_name}
            },
        },
        "WFSerializationType": "WFTextTokenString",
    }


def output_ref(action_uuid, output_name):
    return {
        "Value": {
            "Type": "ActionOutput",
            "OutputUUID": action_uuid,
            "OutputName": output_name,
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def output_ref_as_url(action_uuid, output_name):
    """Reference with URL type coercion (the key fix for 'rich text to URL')."""
    return {
        "Value": {
            "Type": "ActionOutput",
            "OutputUUID": action_uuid,
            "OutputName": output_name,
            "Aggrandizements": [
                {
                    "Type": "WFCoercionVariableAggrandizement",
                    "CoercionItemClass": "WFURLContentItem",
                }
            ],
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def output_text(action_uuid, output_name):
    return {
        "Value": {
            "string": "\ufffc",
            "attachmentsByRange": {
                "{0, 1}": {
                    "Type": "ActionOutput",
                    "OutputUUID": action_uuid,
                    "OutputName": output_name,
                }
            },
        },
        "WFSerializationType": "WFTextTokenString",
    }


def var_ref(var_name):
    return {
        "Value": {"Type": "Variable", "VariableName": var_name},
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
    p = params or {}
    if "UUID" not in p:
        p["UUID"] = new_uuid()
    return {
        "WFWorkflowActionIdentifier": f"is.workflow.actions.{identifier}",
        "WFWorkflowActionParameters": p,
    }


def if_begin(group_id, condition, value=None):
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
    """Full shortcut matching iOS-native format."""
    g_input = new_uuid()
    g_error = new_uuid()
    g_picker = new_uuid()

    # UUIDs for actions whose output we reference
    clipboard_uuid = new_uuid()
    api_post_uuid = new_uuid()
    geturl_uuid = new_uuid()
    download_uuid = new_uuid()
    save_uuid = new_uuid()
    picker_geturl_uuid = new_uuid()
    picker_download_uuid = new_uuid()
    picker_save_uuid = new_uuid()

    actions = []

    # --- Input: Share Sheet or clipboard fallback ---

    # 1. Get Clipboard
    actions.append(act("getclipboard", {"UUID": clipboard_uuid}))

    # 2. Set videoURL from clipboard
    actions.append(act("setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": output_ref(clipboard_uuid, "Clipboard"),
    }))

    # --- API POST (JSON body + headers, matching working shortcut exactly) ---

    # 3. POST to cobalt API
    actions.append(act("downloadurl", {
        "UUID": api_post_uuid,
        "ShowHeaders": True,
        "WFURL": API_URL,
        "WFHTTPMethod": "POST",
        "WFHTTPBodyType": "JSON",
        "WFJSONValues": dict_value([
            dict_item("url", var_text("videoURL")),
            dict_item("videoQuality", text("max")),
            dict_item("filenameStyle", text("pretty")),
            dict_item("youtubeVideoCodec", text("h264")),
        ]),
        "WFHTTPHeaders": dict_value([
            dict_item("Content-Type", text("application/json")),
            dict_item("Accept", text("application/json")),
            dict_item("Authorization", text(f"Api-Key {API_KEY}")),
        ]),
    }))

    # 4. Save API response
    actions.append(act("setvariable", {
        "WFVariableName": "apiResponse",
        "WFInput": output_ref(api_post_uuid, "Contents of URL"),
    }))

    # 5. Get "status" key
    status_uuid = new_uuid()
    actions.append(act("getvalueforkey", {
        "UUID": status_uuid,
        "WFDictionaryKey": "status",
        "WFInput": output_ref(api_post_uuid, "Contents of URL"),
    }))
    actions.append(act("setvariable", {
        "WFVariableName": "status",
        "WFInput": output_ref(status_uuid, "Dictionary Value"),
    }))

    # --- Error check ---

    # 6. IF status contains "error"
    actions.append(act("getvariable", {"WFVariable": var_ref("status")}))
    actions.append(if_begin(g_error, "Contains", "error"))

    # 7. Show error
    error_key_uuid = new_uuid()
    actions.append(act("getvalueforkey", {
        "UUID": error_key_uuid,
        "WFDictionaryKey": "error",
        "WFInput": var_ref("apiResponse"),
    }))
    actions.append(act("setvariable", {
        "WFVariableName": "errorMsg",
        "WFInput": output_ref(error_key_uuid, "Dictionary Value"),
    }))
    actions.append(act("alert", {
        "WFAlertActionTitle": "Download Failed",
        "WFAlertActionMessage": var_text("errorMsg"),
    }))

    # 8. Otherwise (success)
    actions.append(if_else(g_error))

    # --- Picker check (Instagram carousels) ---

    # 9. IF status contains "picker"
    actions.append(act("getvariable", {"WFVariable": var_ref("status")}))
    actions.append(if_begin(g_picker, "Contains", "picker"))

    # 10. Get picker → first item → url
    actions.append(act("getvalueforkey", {
        "WFDictionaryKey": "picker",
        "WFInput": var_ref("apiResponse"),
    }))
    actions.append(act("getitemfromlist", {"WFItemSpecifier": "First Item"}))
    actions.append(act("getvalueforkey", {
        "UUID": picker_geturl_uuid,
        "WFDictionaryKey": "url",
    }))

    # 11. Set downloadURL with URL coercion, download, save, notify
    actions.append(act("setvariable", {
        "WFVariableName": "downloadURL",
        "WFInput": output_ref_as_url(picker_geturl_uuid, "Dictionary Value"),
    }))
    actions.append(act("downloadurl", {
        "UUID": picker_download_uuid,
        "WFURL": var_text("downloadURL"),
        "ShowHeaders": True,
    }))
    actions.append(act("savetocameraroll", {
        "UUID": picker_save_uuid,
        "WFInput": output_ref(picker_download_uuid, "Contents of URL"),
    }))
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 12. Otherwise (tunnel/redirect)
    actions.append(if_else(g_picker))

    # 13. Get url from apiResponse with URL coercion
    actions.append(act("getvalueforkey", {
        "UUID": geturl_uuid,
        "WFDictionaryKey": "url",
        "WFInput": var_ref("apiResponse"),
    }))
    actions.append(act("setvariable", {
        "WFVariableName": "downloadURL",
        "WFInput": output_ref_as_url(geturl_uuid, "Dictionary Value"),
    }))

    # 14. Download, save, notify
    actions.append(act("downloadurl", {
        "UUID": download_uuid,
        "WFURL": var_text("downloadURL"),
        "ShowHeaders": True,
    }))
    actions.append(act("savetocameraroll", {
        "UUID": save_uuid,
        "WFInput": output_ref(download_uuid, "Contents of URL"),
    }))
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))

    # 15. End If (picker)
    actions.append(if_end(g_picker))

    # 16. End If (error)
    actions.append(if_end(g_error))

    return actions


def build_debug_actions():
    """Debug version: shows API response and copies to clipboard."""
    clipboard_uuid = new_uuid()
    api_post_uuid = new_uuid()

    actions = []

    # 1. Get Clipboard → videoURL
    actions.append(act("getclipboard", {"UUID": clipboard_uuid}))
    actions.append(act("setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": output_ref(clipboard_uuid, "Clipboard"),
    }))

    # 2. POST to cobalt API
    actions.append(act("downloadurl", {
        "UUID": api_post_uuid,
        "ShowHeaders": True,
        "WFURL": API_URL,
        "WFHTTPMethod": "POST",
        "WFHTTPBodyType": "JSON",
        "WFJSONValues": dict_value([
            dict_item("url", var_text("videoURL")),
            dict_item("videoQuality", text("max")),
            dict_item("filenameStyle", text("pretty")),
            dict_item("youtubeVideoCodec", text("h264")),
        ]),
        "WFHTTPHeaders": dict_value([
            dict_item("Content-Type", text("application/json")),
            dict_item("Accept", text("application/json")),
            dict_item("Authorization", text(f"Api-Key {API_KEY}")),
        ]),
    }))

    # 3. Save response → Quick Look → Copy to Clipboard
    actions.append(act("setvariable", {
        "WFVariableName": "apiResponse",
        "WFInput": output_ref(api_post_uuid, "Contents of URL"),
    }))
    actions.append(act("getvariable", {"WFVariable": var_ref("apiResponse")}))
    actions.append(act("quicklook"))
    actions.append(act("getvariable", {"WFVariable": var_ref("apiResponse")}))
    actions.append(act("setclipboard"))
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video Debug",
        "WFNotificationActionBody": "API response copied to clipboard.",
    }))

    return actions


def make_shortcut(actions_fn, glyph=59511, color=463140863):
    return {
        "WFWorkflowActions": actions_fn(),
        "WFWorkflowClientVersion": "4407",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": False,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": glyph,
            "WFWorkflowIconStartColor": color,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": [
            "WFAppContentItem",
            "WFAppStoreAppContentItem",
            "WFArticleContentItem",
            "WFContactContentItem",
            "WFDateContentItem",
            "WFEmailAddressContentItem",
            "WFFolderContentItem",
            "WFGenericFileContentItem",
            "WFImageContentItem",
            "WFiTunesProductContentItem",
            "WFLocationContentItem",
            "WFDCMapsLinkContentItem",
            "WFAVAssetContentItem",
            "WFPDFContentItem",
            "WFPhoneNumberContentItem",
            "WFRichTextContentItem",
            "WFSafariWebPageContentItem",
            "WFStringContentItem",
            "WFURLContentItem",
        ],
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowOutputContentItemClasses": [],
        "WFQuickActionSurfaces": [],
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
