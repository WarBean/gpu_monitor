import re
import time
import json
import itchat
import argparse
from threading import Thread, Lock
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

class CustomHandler(BaseHTTPRequestHandler):
    alert_record = { }

    def do_GET(self):
        length = int(self.headers['content-length'])
        info = json.loads(self.rfile.read(length).decode())
        slaver_address, _ = self.client_address
        lock.acquire()
        info_record[slaver_address] = info
        lock.release()
        alert_waste(info, self.alert_record)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def http_func():
    server = HTTPServer((opt.address, opt.port), CustomHandler)
    print("监听服务开启，按<Ctrl-C>退出")
    server.serve_forever()

def alert_condition(mem_usage, gpu_percent, cpu_percent, wechatname, pid, alert_record):
    if mem_usage < opt.mem_usage_threshold: return False
    if cpu_percent > opt.cpu_percent_threshold and gpu_percent > opt.gpu_percent_threshold: return False
    curr_time = time.time()
    if (wechatname, pid) not in alert_record:
        alert_record[(wechatname, pid)] = curr_time
        return True
    if curr_time - alert_record[(wechatname, pid)] > 30:
        alert_record[(wechatname, pid)] = curr_time
        return True
    return False

def alert_waste(info, alert_record):
    for slaver_address in sorted(info_record.keys()):
        gi_list = info_record[slaver_address]['gpu']
        pi_list = info_record[slaver_address]['process']
        for pi in pi_list:
            gi = gi_list[pi['gpuid']]
            if alert_condition(pi['mem_usage'], gi['percent'], pi['cpu_percent'], pi['wechatname'], pi['pid'], alert_record):
                alerting = [
                    '检测到程序长时间高内存消耗且低负载空转：',
                    '所在服务器：%s' % slaver_address,
                    'GPU id：%d' % pi['gpuid'],
                    'PID：%d' % pi['pid'],
                    '程序名：%s' % pi['program'],
                    '进程GPU内存占用：%dM' % pi['mem_usage'],
                    '所在GPU内存占用：%dM/%dM' % (gi['mem_usage'], gi['mem_total']),
                    '所在GPU使用率：%d%%' % gi['percent'],
                    '进程CPU使用率：%d%%' % pi['cpu_percent'],
                ]
                print('向<%s>发送警报：\n\t%s' % (pi['wechatname'], '\n\t'.join(alerting)))
                friend = itchat.search_friends(nickName = pi['wechatname'])
                if len(friend) == 0:
                    print('不存在微信好友：<%s>' % pi['wechatname'])
                    continue
                friend[0].send('\n'.join(alerting))

def report_server():
    report = ['服务器列表：']
    lock.acquire()
    for slaver_address in sorted(info_record.keys()):
        report.append(slaver_address)
    lock.release()
    report = '\n'.join(report)
    return report

def report_gpu(slaver_address = None):
    report = []
    lock.acquire()
    if slaver_address is None:
        address_list = sorted(info_record.keys())
    else:
        address_list = [slaver_address]
    for slaver_address in address_list:
        report.append('服务器地址: %s' % slaver_address)
        gi_list = info_record[slaver_address]['gpu']
        pi_list = info_record[slaver_address]['process']
        for gpuid, gi in enumerate(gi_list):
            report.append('GPU%d 显存%dM/%dM 使用率%d%%' % (
                gpuid, int(gi['mem_usage']), int(gi['mem_total']), int(gi['percent'])
            ))
        report.append('进程列表')
        for pi in pi_list:
            report.append('GPU%d %s %s 显存%dM CPU占比%d%%' % (
                pi['gpuid'], pi['username'], pi['wechatname'], int(pi['mem_usage']), int(pi['cpu_percent'])
            ))
        report.append('=' * 10)
    if report != []: del report[-1]
    lock.release()
    report = '\n'.join(report)
    return report

def report_user():
    usage_dict = { }
    lock.acquire()
    for slaver_address in sorted(info_record.keys()):
        pi_list = info_record[slaver_address]['process']
        for pi in pi_list:
            wechatname = pi['wechatname']
            mem_usage = pi['mem_usage']
            usage_dict[wechatname] = usage_dict.get(wechatname, 0) + mem_usage
    lock.release()
    usage_list = sorted(usage_dict.items(), key = lambda x: x[1])
    report = ['用户显存占用排序：'] + ['%s : %dM' % (n, u) for n, u in usage_list]
    report = '\n'.join(report)
    return report

parser = argparse.ArgumentParser()
parser.add_argument('--address', required = True, help = 'master服务器IP地址')
parser.add_argument('--port', type = int, default = '5678', help = 'master服务器端口，默认5678')
parser.add_argument('--interval', type = int, default = '1800', help = '警报间隔时间，默认1800秒')
parser.add_argument('--mem_usage_threshold', type = int, default = '1000', help = '警报功能GPU内存阈值')
parser.add_argument('--gpu_percent_threshold', type = int, default = '10', help = '警报功能GPU使用率阈值')
parser.add_argument('--cpu_percent_threshold', type = int, default = '10', help = '警报功能CPU使用率阈值')
opt = parser.parse_args()

info_record = { }
lock = Lock()

http_thread = Thread(target = http_func)
http_thread.setDaemon(True)
http_thread.start()

@itchat.msg_register(itchat.content.TEXT)
def receive_text(msg):
    print('收到指令: %s' % msg.text)
    error = '\n'.join([
        '请使用有效指令：',
        'user：查看用户使用情况',
        'server：查看服务器列表',
        'gpu：查看所有GPU使用情况',
        'gpu <完整IP地址或后缀>：查看指定服务器GPU使用情况',
    ])
    if msg.text == 'server':
        return report_server()
    if msg.text.startswith('gpu'):
        if msg.text == 'gpu':
            return report_gpu()
        tokens = msg.text.split()
        if len(tokens) != 2:
            return error
        slaver_address = tokens[1]
        if not re.fullmatch('\d+\.\d+\.\d+\.\d+', slaver_address):
            candidates = [add for add in info_record.keys() if add.endswith(slaver_address)]
            if len(candidates) == 0:
                return '服务器%s不存在' % slaver_address
            if len(candidates) > 1:
                report = ['请指明是以下哪个服务器：'] + candidates
                return '\n'.join(report)
            slaver_address = candidates[0]
        if slaver_address not in info_record:
            return '服务器%s不存在' % slaver_address
        return report_gpu(slaver_address)
    if msg.text in ['用户', 'user']:
        return report_user()
    return error

itchat.auto_login(enableCmdQR = 2, hotReload = True)
itchat.run()
