# -*- coding: utf-8 -*-

import json

kb_start = {
    "one_time": True,
    "buttons": [
        [
            {
                "action": {
                    "type": "text",
                    "label": "Начать"
                },
                "color": "primary"
            }
        ]
    ]
}

kb_start = json.dumps(kb_start, ensure_ascii=False).encode('utf-8')
kb_start = str(kb_start.decode('utf-8'))
