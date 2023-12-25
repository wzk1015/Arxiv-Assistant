import openai
import json

from assistant import ArxivAssistant

with open("openai_key.txt") as f:
    openai.api_key = f.read().strip()
    
with open("mail_info.json") as f:
    mail_info = json.load(f)

assistant = ArxivAssistant(
    mail_host=mail_info["mail_host"],
    mail_user=mail_info["mail_user"],    #发送邮箱的用户名，如xxxxxx@qq.com
    mail_pass=mail_info["mail_pass"],  #发送邮箱的密码（注：QQ邮箱需要开启SMTP服务后在此填写授权码）
    
    categories=['cs.CV', 'cs.CL', 'cs.LG', 'cs.MA', 'cs.MM', 'cs.AI', 'cs.SD'], 
    keywords=['large language model', 'LLM', 'vision backbone', 'object detection', 'minecraft', 'agent', 'learning representation', 'multimodal',
                'music generation', 'vision transformer', 'ViT'],
    negative_keywords=['3D', 'medical'],
    
    mail_receivers=mail_info.get("mail_receivers", None),
    gpt_filter=False,
    
    # routine_interval_hours=0.0000001,
)
# assistant.query_gpt("123")
assistant.run_routine()