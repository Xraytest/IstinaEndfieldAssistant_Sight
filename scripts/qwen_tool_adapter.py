#!C:\Users\cheng\Documents\ArkStudio\IstinaAI\IstinaEndfieldAssistant_Sight\3rd-part\python\python.exe
"""
Qwen3.6 宸ュ叿璋冪敤閫傞厤灞?鈥?鐢变簬 Qwen3.6 涓嶆敮鎸佸師鐢?tool_calling锛?闇€瑕侀€氳繃鑷畾涔夋牸寮忚В鏋愬疄鐜般€?
宸ヤ綔鏈哄埗锛?1. 鍦?system prompt 涓畾涔夊彲鐢ㄥ伐鍏峰強鍏跺弬鏁版牸寮?2. Qwen3.6 浠ョ壒瀹?XML/JSON 鏍煎紡杩斿洖宸ュ叿璋冪敤
3. 姝ら€傞厤灞傝В鏋愯繑鍥炲唴瀹癸紝鎻愬彇宸ュ叿璋冪敤骞舵墽琛?4. 鎵ц缁撴灉閲嶆柊娉ㄥ叆瀵硅瘽涓婁笅鏂?
宸ュ叿鍒楄〃锛?- tap(x, y) - 鐐瑰嚮鍧愭爣
- swipe(x1,y1,x2,y2,duration) - 婊戝姩
- screenshot() -> base64 - 鎴浘
- ocr() -> list - OCR 璇嗗埆
- wait(seconds) - 绛夊緟
- navigate(target) - 瀵艰埅鍒扮洰鏍囬〉闈?- collect_entity(name) - 閲囬泦瀹炰綋鍥惧儚
"""

import json, re, time, base64, os, subprocess
from typing import Dict, List, Any, Optional, Callable

# 鈹€鈹€ 宸ュ叿瀹氫箟 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

TOOL_DEFINITIONS = {
    "tap": {
        "description": "鐐瑰嚮灞忓箷鎸囧畾浣嶇疆",
        "params": {"x": "int (0-1280)", "y": "int (0-720)"},
        "examples": '{"action":"tap","x":640,"y":360}',
    },
    "swipe": {
        "description": "婊戝姩",
        "params": {"x1": "int", "y1": "int", "x2": "int", "y2": "int", "duration_ms": "int"},
        'examples': '{"action":"swipe","x1":500,"y1":300,"x2":500,"y2":600,"duration_ms":500}',
    },
    "screenshot": {
        "description": "鎴浘骞惰繑鍥瀊ase64缂栫爜",
        "params": {},
        "examples": '{"action":"screenshot"}',
    },
    "ocr": {
        "description": "OCR璇嗗埆褰撳墠灞忓箷鏂囧瓧",
        "params": {},
        "examples": '{"action":"ocr"}',
    },
    "wait": {
        "description": "绛夊緟鎸囧畾绉掓暟",
        "params": {"seconds": "float"},
        "examples": '{"action":"wait","seconds":3.0}',
    },
    "navigate": {
        "description": "瀵艰埅鍒版寚瀹氭父鎴忛〉闈?,
        "params": {"target": "str: exploration/industry/event_center/signin/dungeon/combat/encyclopedia"},
        "examples": '{"action":"navigate","target":"event_center"}',
    },
    "collect": {
        "description": "閲囬泦褰撳墠鐢婚潰涓殑瀹炰綋鍥惧儚",
        "params": {
            "entity_name": "str: 瀹炰綋鍚嶇О",
            "variation": "str: normal/combat/skill/damaged/idle",
            "angle": "str: front/side/back/top",
        },
        "examples": '{"action":"collect","entity_name":"surge_tower","variation":"idle","angle":"front"}',
    },
    "move": {
        "description": "绉诲姩瑙掕壊鍒版寚瀹氭柟鍚?,
        "params": {"direction": "str: forward/left/right/back/forward_left/forward_right/back_left/back_right"},
        "examples": '{"action":"move","direction":"forward"}',
    },
    "analyze_screen": {
        "description": "鐢ㄨ瑙夋ā鍨嬪垎鏋愬綋鍓嶇敾闈㈠唴瀹?,
        "params": {"question": "str: 鍒嗘瀽闂"},
        "examples": '{"action":"analyze_screen","question":"鐢婚潰涓湁鍝簺鏁屼汉锛?}',
    },
}

TOOL_SYSTEM_PROMPT = f"""浣犳槸 IEA 娓告垙瀹炰綋閲囬泦鍔╂墜銆備綘鍙互浣跨敤浠ヤ笅宸ュ叿涓庣幆澧冧氦浜掞細

鍙敤宸ュ叿锛堜互 JSON 鏍煎紡杩斿洖锛屾瘡琛屼竴涓姩浣滐紝鏀寔澶氫釜鍔ㄤ綔椤哄簭鎵ц锛夛細

{json.dumps(TOOL_DEFINITIONS, ensure_ascii=False, indent=2)}

杩斿洖鏍煎紡瑕佹眰锛?1. 姣忎釜鍔ㄤ綔鍗曠嫭涓€琛?JSON
2. 澶氫釜鍔ㄤ綔鎸夋墽琛岄『搴忔帓鍒?3. 鍏堟€濊€冨悗杈撳嚭鍔ㄤ綔
4. 鍔ㄤ綔琛屼互 >>> 寮€澶?
绀轰緥锛?鎴戞兂鐭ラ亾褰撳墠鐢婚潰鏈変粈涔?>>> {{"action":"screenshot"}}
>>> {{"action":"analyze_screen","question":"鎻忚堪鐢婚潰鍐呭"}}

鎴戣绉诲姩鍒版晫浜洪潰鍓嶆敾鍑?>>> {{"action":"move","direction":"forward"}}
>>> {{"action":"move","direction":"forward"}}
>>> {{"action":"wait","seconds":2}}
>>> {{"action":"screenshot"}}
>>> {{"action":"analyze_screen","question":"鏁屼汉浣嶇疆鍦ㄥ摢閲岋紵"}}
"""


# 鈹€鈹€ 鍔ㄤ綔瑙ｆ瀽鍣?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class QwenToolExecutor:
    """瑙ｆ瀽 Qwen3.6 杈撳嚭涓殑宸ュ叿璋冪敤骞舵墽琛?""

    def __init__(self, tool_impls: Dict[str, Callable] = None):
        self.tool_impls = tool_impls or {}
        self.execution_log = []

    def register_tool(self, name: str, impl: Callable):
        self.tool_impls[name] = impl

    def parse_actions(self, qwen_response: str) -> List[Dict]:
        """浠?Qwen 鍥炲涓В鏋愬姩浣滃垪琛?""
        actions = []

        # 妯″紡1: >>> {"action":"..."} 鏍煎紡锛堟帹鑽愶級
        for line in qwen_response.split('\n'):
            line = line.strip()
            if line.startswith('>>>'):
                line = line[3:].strip()
                try:
                    action = json.loads(line)
                    if isinstance(action, dict) and 'action' in action:
                        actions.append(action)
                except json.JSONDecodeError:
                    continue

        # 妯″紡2: 鐙珛 JSON 琛?        if not actions:
            for line in qwen_response.split('\n'):
                line = line.strip()
                try:
                    action = json.loads(line)
                    if isinstance(action, dict) and 'action' in action:
                        actions.append(action)
                except json.JSONDecodeError:
                    continue

        return actions

    def execute_action(self, action: Dict) -> Dict:
        """鎵ц鍗曚釜鍔ㄤ綔"""
        action_type = action.get('action', '')
        params = {k: v for k, v in action.items() if k != 'action'}

        impl = self.tool_impls.get(action_type)
        if impl:
            try:
                result = impl(**params)
                self.execution_log.append({
                    'action': action_type,
                    'params': params,
                    'success': True,
                    'result': str(result)[:500],
                })
                return {'success': True, 'result': result}
            except Exception as e:
                self.execution_log.append({
                    'action': action_type,
                    'params': params,
                    'success': False,
                    'error': str(e),
                })
                return {'success': False, 'error': str(e)}
        else:
            return {'success': False, 'error': f'Unknown tool: {action_type}'}

    def execute_actions(self, actions: List[Dict]) -> List[Dict]:
        """椤哄簭鎵ц澶氫釜鍔ㄤ綔"""
        results = []
        for action in actions:
            result = self.execute_action(action)
            results.append(result)
            if not result['success']:
                break
        return results

    def build_feedback(self, results: List[Dict]) -> str:
        """鏋勫缓鎵ц鍙嶉鍥?Qwen"""
        feedback_parts = []
        for i, (action, result) in enumerate(zip(
            [a for r in results for a in [r]], results
        )):
            status = "SUCCESS" if result['success'] else "FAILED"
            feedback_parts.append(
                f"Step {i+1}: {json.dumps(action)} 鈫?{status}"
            )
        return '\n'.join(feedback_parts)


# 鈹€鈹€ 瀹炰綋閲囬泦绠＄嚎 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

ENTITY_COLLECTOR_PROMPT = """浣犳槸 IEA 娓告垙瀹炰綋鍥惧儚閲囬泦涓撳銆?
浠诲姟锛氬湪銆婃槑鏃ユ柟鑸燂細缁堟湯鍦般€嬩腑锛屼负鎸囧畾瀹炰綋鏀堕泦澶氳搴︺€佸褰㈡€佺殑璁粌鍥惧儚銆?
褰撳墠鐩爣瀹炰綋锛歿entity_name}
宸叉湁姝ゅ疄浣撳浘鍍忥細{existing_count} 寮?鐩爣锛?000 寮?
閲囬泦绛栫暐锛?1. 鍏堢‘璁ゅ綋鍓嶆墍鍦ㄤ綅缃?2. 鍓嶅線璇ュ疄浣撳彲鑳藉嚭鐜扮殑鍦扮偣锛堝壇鏈€侀噹澶栥€佹嵁鐐癸級
3. 浠庝笉鍚岃搴︼紙姝ｉ潰銆佷晶闈€佽儗闈€佷刊瑙嗭級鎷嶆憚
4. 鍦ㄤ笉鍚岀姸鎬侊紙寰呮満銆佺Щ鍔ㄣ€佹敾鍑汇€佹妧鑳姐€佸彈鍑伙級涓嬫媿鎽?5. 鍦ㄤ笉鍚屽厜鐓э紙鐧藉ぉ銆佸鏅氥€佹妧鑳界壒鏁堬級涓嬫媿鎽?
娉ㄦ剰锛?- 姣忓紶鎴浘鍚庣珛鍗充繚瀛樺苟鍒嗘瀽
- 纭繚瑙掑害宸紓瓒冲澶э紙鐩镐技搴?> 30% 鎵嶄繚鐣欙級
- 閬垮厤閲嶅閲囬泦鐩稿悓瑙掑害
- 濡傛灉褰撳墠鍖哄煙娌℃湁鐩爣瀹炰綋锛屽皾璇曞鑸埌鍏朵粬鍖哄煙

璇蜂竴姝ユ鎵ц锛屾瘡娆¤繑鍥?1-5 涓姩浣溿€?"""


# 鈹€鈹€ 涓诲惊鐜?鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

class EntityCollectionPipeline:
    """鑷富瀹炰綋閲囬泦绠＄嚎"""

    def __init__(self, executor: QwenToolExecutor, qwen_api_func: Callable):
        self.executor = executor
        self.qwen = qwen_api_func
        self.collected = {}  # entity_name -> [file_paths]
        self.session_log = []

    def collect_entity(self, entity_name: str, target_count: int = 1000):
        """涓烘寚瀹氬疄浣撻噰闆嗗浘鍍忕洿鍒扮洰鏍囨暟閲?""
        existing = self.collected.get(entity_name, [])
        print(f"\n=== 寮€濮嬮噰闆?[{entity_name}] {len(existing)}/{target_count} ===")

        while len(existing) < target_count:
            # 璁?Qwen 鍐冲畾涓嬩竴姝ュ姩浣?            prompt = ENTITY_COLLECTOR_PROMPT.format(
                entity_name=entity_name,
                existing_count=len(existing),
            )

            # 娣诲姞涓婃鎵ц鍙嶉
            if self.session_log:
                recent = self.session_log[-5:]
                prompt += "\n\n鏈€杩戞墽琛岃褰曪細\n" + '\n'.join(recent)

            response = self.qwen(prompt)
            actions = self.executor.parse_actions(response)

            if not actions:
                print(f"  Qwen 鏈繑鍥炴湁鏁堝姩浣滐紝绛夊緟鍚庨噸璇?)
                time.sleep(3)
                continue

            results = self.executor.execute_actions(actions)
            feedback = self.executor.build_feedback(
                list(zip(actions, results))
            )
            self.session_log.append(feedback)

            # 妫€鏌ユ槸鍚︽湁鎴浘琚繚瀛?            for action, result in zip(actions, results):
                if action.get('action') == 'collect' and result.get('success'):
                    existing = self.collected.get(entity_name, [])
                    print(f"  Progress: {len(existing)}/{target_count}")

        print(f"=== [{entity_name}] 閲囬泦瀹屾垚: {len(existing)} 寮?===")

