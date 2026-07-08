import re
from pathlib import Path

text = Path('C:/Users/cheng/.kimi-code/sessions/wd_istinaendfieldassistant_sight_94404cad406e/session_de73c248-dbc7-4573-b396-a09b6df37e00/agents/main/tool-results/AgentSwarm-chatcmpl-tool-917ed3562cd35a49-e1b7acad-8bee-4931-a9c0-67860e71331f.txt').read_text(encoding='utf-8')

# Extract all subagent results
pattern = re.compile(r'<subagent agent_id="[^"]+" item="([^"]+)" outcome="completed">(.*?)</subagent>', re.DOTALL)
matches = pattern.findall(text)

anomalies = []
for item, content in matches:
    # Find anomaly count
    count_match = re.search(r'异常数量:\s*(\d+)', content)
    if count_match:
        count = int(count_match.group(1))
        if count > 0:
            # Extract anomaly details
            anomaly_section = re.search(r'异常:\s*(.*?)(?:\n\n正常函数|\Z)', content, re.DOTALL)
            if anomaly_section:
                anomaly_text = anomaly_section.group(1).strip()
                anomalies.append((item, anomaly_text))

print(f'Total files with anomalies: {len(anomalies)}')
print()
for item, anomaly_text in anomalies:
    print(f'=== {item} ===')
    print(anomaly_text)
    print()
