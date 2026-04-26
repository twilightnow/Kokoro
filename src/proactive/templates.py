from ..personality.character import CharacterConfig
from .action import ProactiveScene

_SHORT_TEMPLATES: dict[ProactiveScene, str] = {
    "late_night": "已经很晚了，别太勉强自己。",
    "long_work": "你已经忙了很久，要不要起来活动一下？",
    "idle_return": "你回来了呀，刚才有休息到吗？",
    "window_switch": "你切来切去像是在犹豫，要不要先缓一下？",
    "gaming": "我先安静陪着你，不多打扰。",
    "reminder": "到约好的时间了，我来提醒你。",
}
_DEFAULT_EXPRESSIONS: dict[ProactiveScene, str] = {
    "late_night": "cold",
    "long_work": "cold",
    "idle_return": "happy",
    "window_switch": "normal",
    "gaming": "happy",
    "reminder": "normal",
}
_QUICK_ACTIONS: dict[ProactiveScene, list[str]] = {
    "late_night": ["知道了", "稍后休息", "今天别提醒"],
    "long_work": ["知道了", "稍后提醒", "今天别提醒"],
    "idle_return": ["我回来了", "稍后聊", "今天别提醒"],
    "window_switch": ["让我想想", "稍后提醒", "今天别提醒"],
    "gaming": ["收到", "继续陪我", "今天别提醒"],
    "reminder": ["知道了", "稍后提醒", "今天别提醒"],
}


def short_template_for_scene(scene: ProactiveScene) -> str:
    return _SHORT_TEMPLATES.get(scene, "我在这里陪着你。")


def expression_for_scene(scene: ProactiveScene) -> str:
    return _DEFAULT_EXPRESSIONS.get(scene, "normal")


def quick_actions_for_scene(scene: ProactiveScene) -> list[str]:
    return list(_QUICK_ACTIONS.get(scene, ["知道了", "稍后提醒", "今天别提醒"]))


def style_hint_for_scene(character: CharacterConfig, scene: ProactiveScene) -> str:
    style = character.proactive_style
    mapping = {
        "late_night": style.user_working_late,
        "long_work": style.user_working_late,
        "idle_return": style.idle_too_long,
        "window_switch": style.idle_too_long,
        "gaming": style.user_gaming,
        "reminder": style.idle_too_long,
    }
    return mapping.get(scene, "")