#!/usr/bin/env python3
"""Generate 'Save Video' iOS Shortcut (.shortcut binary plist)
Format reverse-engineered from working iOS-built shortcut (Feb 2026).
Key patterns: WFHTTPBodyType JSON + WFJSONValues, explicit WFInput ActionOutput
refs with UUIDs, WFCoercionVariableAggrandizement for URL type coercion.
"""
import plistlib
import uuid
import os

API_URL = "https://cobalt-proxy-production.up.railway.app/"
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


def shortcut_input():
    return {
        "Value": {"Type": "ExtensionInput"},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def shortcut_input_as_url():
    """Share Sheet input coerced to URL type."""
    return {
        "Value": {
            "Type": "ExtensionInput",
            "Aggrandizements": [
                {
                    "Type": "WFCoercionVariableAggrandizement",
                    "CoercionItemClass": "WFURLContentItem",
                }
            ],
        },
        "WFSerializationType": "WFTextTokenAttachment",
    }


def var_ref(var_name):
    return {
        "Value": {"Type": "Variable", "VariableName": var_name},
        "WFSerializationType": "WFTextTokenAttachment",
    }


def var_ref_as_url(var_name):
    """Variable reference coerced to URL type (strips surrounding text)."""
    return {
        "Value": {
            "Type": "Variable",
            "VariableName": var_name,
            "Aggrandizements": [
                {
                    "Type": "WFCoercionVariableAggrandizement",
                    "CoercionItemClass": "WFURLContentItem",
                }
            ],
        },
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
    """Full shortcut with error handling, picker (Instagram carousels),
    and tunnel/redirect download. Uses flat (non-nested) conditionals.
    YouTube uses tunnel (proxied via Webshare residential proxy).
    Twitter uses redirect (direct CDN). Instagram needs session cookies.
    """
    g_error = new_uuid()
    g_picker = new_uuid()
    g_handled = new_uuid()

    api_post_uuid = new_uuid()
    geturl_uuid = new_uuid()
    download_uuid = new_uuid()

    actions = []

    # --- Input: Share Sheet URL or clipboard (via WFWorkflowNoInputBehavior) ---
    # Set videoURL directly from ExtensionInput (Share Sheet passes URL type)
    # When no Share Sheet input, GetClipboard fallback provides clipboard content
    actions.append(act("setvariable", {
        "WFVariableName": "videoURL",
        "WFInput": shortcut_input(),
    }))

    # --- Notification ---
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Downloading...",
    }))

    # --- POST to cobalt API ---
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

    # --- Get status ---
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

    # --- Error check (flat, not nested) ---
    actions.append(act("getvariable", {"WFVariable": var_ref("status")}))
    actions.append(if_begin(g_error, "Contains", "error"))
    actions.append(act("setvariable", {
        "WFVariableName": "handled",
        "WFInput": text("yes"),
    }))
    actions.append(act("alert", {
        "WFAlertActionTitle": "Couldn't Save Video",
        "WFAlertActionMessage": "This video couldn't be downloaded. "
            "Make sure the link is valid and the content is publicly available.",
        "WFAlertActionCancelButtonShown": False,
    }))
    actions.append(if_end(g_error))

    # --- Picker check for Instagram carousels (flat, not nested) ---
    actions.append(act("getvariable", {"WFVariable": var_ref("status")}))
    actions.append(if_begin(g_picker, "Contains", "picker"))
    actions.append(act("setvariable", {
        "WFVariableName": "handled",
        "WFInput": text("yes"),
    }))

    picker_key_uuid = new_uuid()
    actions.append(act("getvalueforkey", {
        "UUID": picker_key_uuid,
        "WFDictionaryKey": "picker",
        "WFInput": output_ref(api_post_uuid, "Contents of URL"),
    }))

    loop_id = new_uuid()
    repeat_uuid = new_uuid()
    actions.append(act("repeat.each", {
        "UUID": repeat_uuid,
        "GroupingIdentifier": loop_id,
        "WFControlFlowMode": 0,
        "WFInput": output_ref(picker_key_uuid, "Dictionary Value"),
    }))

    item_url_uuid = new_uuid()
    actions.append(act("getvalueforkey", {
        "UUID": item_url_uuid,
        "WFDictionaryKey": "url",
        "WFInput": output_ref(repeat_uuid, "Repeat Item"),
    }))
    actions.append(act("setvariable", {
        "WFVariableName": "downloadURL",
        "WFInput": output_ref_as_url(item_url_uuid, "Dictionary Value"),
    }))
    item_dl_uuid = new_uuid()
    actions.append(act("downloadurl", {
        "UUID": item_dl_uuid,
        "WFURL": var_text("downloadURL"),
        "ShowHeaders": True,
    }))
    actions.append(act("savetocameraroll", {
        "WFInput": output_ref(item_dl_uuid, "Contents of URL"),
    }))

    actions.append(act("repeat.each", {
        "GroupingIdentifier": loop_id,
        "WFControlFlowMode": 2,
    }))
    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "All items saved!",
    }))
    actions.append(if_end(g_picker))

    # --- Tunnel/redirect download (only if not already handled) ---
    actions.append(act("getvariable", {"WFVariable": var_ref("handled")}))
    actions.append(if_begin(g_handled, "Has Any Value"))
    actions.append(if_else(g_handled))

    actions.append(act("getvalueforkey", {
        "UUID": geturl_uuid,
        "WFDictionaryKey": "url",
        "WFInput": output_ref(api_post_uuid, "Contents of URL"),
    }))

    # Facebook URLs break with URL coercion, everything else needs it
    g_facebook = new_uuid()
    actions.append(act("getvariable", {"WFVariable": var_ref("videoURL")}))
    actions.append(if_begin(g_facebook, "Contains", "facebook"))

    # --- Facebook path: no URL coercion ---
    fb_dl_uuid = new_uuid()
    actions.append(act("setvariable", {
        "WFVariableName": "downloadURL",
        "WFInput": output_ref(geturl_uuid, "Dictionary Value"),
    }))
    actions.append(act("downloadurl", {
        "UUID": fb_dl_uuid,
        "WFURL": var_text("downloadURL"),
        "ShowHeaders": True,
    }))
    actions.append(act("savetocameraroll", {
        "WFInput": output_ref(fb_dl_uuid, "Contents of URL"),
    }))

    actions.append(if_else(g_facebook))

    # --- Default path: URL coercion (Twitter, YouTube, Instagram) ---
    actions.append(act("setvariable", {
        "WFVariableName": "downloadURL",
        "WFInput": output_ref_as_url(geturl_uuid, "Dictionary Value"),
    }))
    actions.append(act("downloadurl", {
        "UUID": download_uuid,
        "WFURL": var_text("downloadURL"),
        "ShowHeaders": True,
    }))
    actions.append(act("savetocameraroll", {
        "WFInput": output_ref(download_uuid, "Contents of URL"),
    }))

    actions.append(if_end(g_facebook))

    actions.append(act("notification", {
        "WFNotificationActionTitle": "Save Video",
        "WFNotificationActionBody": "Video saved!",
    }))
    actions.append(if_end(g_handled))

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


def make_shortcut(actions_fn, glyph=59746, color=946986751):
    return {
        "WFWorkflowActions": actions_fn(),
        "WFWorkflowClientVersion": "4407",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": glyph,
            "WFWorkflowIconStartColor": color,
        },
        "WFWorkflowImportQuestions": [],
        "WFWorkflowNoInputBehavior": {
            "Name": "WFWorkflowNoInputBehaviorGetClipboard",
            "Parameters": {},
        },
        "WFWorkflowInputContentItemClasses": [
            "WFURLContentItem",
            "WFStringContentItem",
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


def generate_and_sign(name, actions_fn, color=946986751, glyph=59746):
    base = os.path.dirname(os.path.abspath(__file__))
    unsigned = os.path.join(base, f"{name}.shortcut")
    signed = os.path.join(base, f"{name} (Signed).shortcut")

    shortcut = make_shortcut(actions_fn, glyph=glyph, color=color)
    with open(unsigned, "wb") as f:
        plistlib.dump(shortcut, f, fmt=plistlib.FMT_BINARY)
    print(f"Generated: {name}.shortcut ({os.path.getsize(unsigned)} bytes)")
    sign_shortcut(unsigned, signed)


if __name__ == "__main__":
    generate_and_sign("Save Video", build_actions)
    generate_and_sign("Save Video Debug", build_debug_actions, color=4282601983, glyph=59493)

    print()
    print("Install on iPhone (open in Safari):")
    print("  Main:  https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20(Signed).shortcut")
    print("  Debug: https://github.com/chrisb4096-alt/cobalt-downloader/raw/master/Save%20Video%20Debug%20(Signed).shortcut")
