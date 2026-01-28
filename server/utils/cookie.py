import requests
from config.config import cfg

async def get_cookie(input1, input2):
    mes = ""
    if cfg['get_cookie']['url']:
        for x in cfg['get_cookie']['url']:
            data = {"input1": input1, "input2": input2, "pass": cfg['get_cookie']['pass']}
            res = requests.post(x['url'], json=data)
            if res.status_code == 200:
                data = res.json()
                igneous = data.get('result', '')
                if igneous or not igneous != '' or not igneous != 'null' or not igneous != 'mystery':
                    mes+=f"{x['name']}: <code>{igneous}</code>\n"
                elif not igneous:
                    mes+=f"{x['name']}: 错误! {res.json().get('error', '')}\n"
                elif igneous == 'mystery':
                    mes+=f"{x['name']}: 您的账号不属于该地区\n"
                    
        return mes