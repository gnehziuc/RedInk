"""
账号管理 API 路由

提供账号的 CRUD 操作、Cookie 管理和扫码登录接口
"""
import asyncio
import sqlite3
import threading
import time
import logging
from queue import Queue
from flask import Blueprint, request, jsonify, Response, send_from_directory

from backend.account_utils.config import DB_PATH, COOKIES_DIR
from backend.account_utils.auth import check_cookie
from backend.account_utils.login import (
    init_database,
    douyin_cookie_gen,
    get_tencent_cookie,
    get_ks_cookie,
    xiaohongshu_cookie_gen
)

logger = logging.getLogger(__name__)

# 存储活跃的 SSE 队列
active_queues = {}


def create_account_blueprint():
    """创建账号管理蓝图"""
    account_bp = Blueprint('accounts', __name__)
    
    # 确保数据库已初始化
    init_database()
    
    @account_bp.route('/accounts', methods=['GET'])
    def get_accounts():
        """获取所有账号（快速，不验证 Cookie）"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM user_info')
                rows = cursor.fetchall()
                rows_list = [list(row) for row in rows]
                
                logger.info(f"📋 获取账号列表: {len(rows_list)} 个账号")
                return jsonify({
                    "code": 200,
                    "msg": None,
                    "data": rows_list
                }), 200
        except Exception as e:
            logger.error(f"获取账号列表失败: {str(e)}")
            return jsonify({
                "code": 500,
                "msg": f"获取账号列表失败: {str(e)}",
                "data": None
            }), 500

    @account_bp.route('/accounts/valid', methods=['GET'])
    async def get_valid_accounts():
        """获取所有账号（带 Cookie 验证）"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM user_info')
                rows = cursor.fetchall()
                rows_list = [list(row) for row in rows]
                
                # 验证每个账号的 Cookie
                for row in rows_list:
                    flag = await check_cookie(row[1], row[2])
                    if not flag:
                        row[4] = 0
                        cursor.execute('''
                            UPDATE user_info 
                            SET status = ? 
                            WHERE id = ?
                        ''', (0, row[0]))
                        conn.commit()
                        logger.info(f"⚠️ 账号 {row[3]} Cookie 已失效")
                    else:
                        row[4] = 1
                        cursor.execute('''
                            UPDATE user_info 
                            SET status = ? 
                            WHERE id = ?
                        ''', (1, row[0]))
                        conn.commit()
                
                return jsonify({
                    "code": 200,
                    "msg": None,
                    "data": rows_list
                }), 200
        except Exception as e:
            logger.error(f"验证账号失败: {str(e)}")
            return jsonify({
                "code": 500,
                "msg": f"验证账号失败: {str(e)}",
                "data": None
            }), 500

    @account_bp.route('/accounts/<int:account_id>', methods=['DELETE'])
    def delete_account(account_id):
        """删除账号"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
                record = cursor.fetchone()
                
                if not record:
                    return jsonify({
                        "code": 404,
                        "msg": "账号不存在",
                        "data": None
                    }), 404
                
                record = dict(record)
                
                # 删除 Cookie 文件
                cookie_path = COOKIES_DIR / record['filePath']
                if cookie_path.exists():
                    try:
                        cookie_path.unlink()
                        logger.info(f"✅ Cookie 文件已删除: {cookie_path}")
                    except Exception as e:
                        logger.warning(f"⚠️ 删除 Cookie 文件失败: {e}")
                
                # 删除数据库记录
                cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
                conn.commit()
                
                logger.info(f"✅ 账号已删除: {record['userName']}")
                return jsonify({
                    "code": 200,
                    "msg": "账号删除成功",
                    "data": None
                }), 200
        except Exception as e:
            logger.error(f"删除账号失败: {str(e)}")
            return jsonify({
                "code": 500,
                "msg": f"删除失败: {str(e)}",
                "data": None
            }), 500

    @account_bp.route('/accounts/<int:account_id>', methods=['PUT'])
    def update_account(account_id):
        """更新账号信息"""
        data = request.get_json()
        type_val = data.get('type')
        user_name = data.get('userName')
        
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE user_info
                    SET type = ?,
                        userName = ?
                    WHERE id = ?
                ''', (type_val, user_name, account_id))
                conn.commit()
                
                logger.info(f"✅ 账号已更新: {user_name}")
                return jsonify({
                    "code": 200,
                    "msg": "账号更新成功",
                    "data": None
                }), 200
        except Exception as e:
            logger.error(f"更新账号失败: {str(e)}")
            return jsonify({
                "code": 500,
                "msg": f"更新失败: {str(e)}",
                "data": None
            }), 500

    @account_bp.route('/accounts/login', methods=['GET'])
    def login():
        """SSE 扫码登录接口"""
        # 1=小红书 2=视频号 3=抖音 4=快手
        type_val = request.args.get('type')
        account_id = request.args.get('id')
        
        status_queue = Queue()
        active_queues[account_id] = status_queue
        
        # 启动异步任务线程
        thread = threading.Thread(
            target=run_async_function,
            args=(type_val, account_id, status_queue),
            daemon=True
        )
        thread.start()
        
        response = Response(sse_stream(status_queue), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no'
        response.headers['Content-Type'] = 'text/event-stream'
        response.headers['Connection'] = 'keep-alive'
        return response

    @account_bp.route('/accounts/cookie/upload', methods=['POST'])
    def upload_cookie():
        """上传 Cookie 文件"""
        try:
            if 'file' not in request.files:
                return jsonify({
                    "code": 500,
                    "msg": "没有找到 Cookie 文件",
                    "data": None
                }), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({
                    "code": 500,
                    "msg": "Cookie 文件名不能为空",
                    "data": None
                }), 400
            
            if not file.filename.endswith('.json'):
                return jsonify({
                    "code": 500,
                    "msg": "Cookie 文件必须是 JSON 格式",
                    "data": None
                }), 400
            
            account_id = request.form.get('id')
            platform = request.form.get('platform')
            
            if not account_id or not platform:
                return jsonify({
                    "code": 500,
                    "msg": "缺少账号 ID 或平台信息",
                    "data": None
                }), 400
            
            # 从数据库获取账号的文件路径
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT filePath FROM user_info WHERE id = ?', (account_id,))
                result = cursor.fetchone()
            
            if not result:
                return jsonify({
                    "code": 500,
                    "msg": "账号不存在",
                    "data": None
                }), 404
            
            # 保存上传的 Cookie 文件
            cookie_file_path = COOKIES_DIR / result['filePath']
            cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
            file.save(str(cookie_file_path))
            
            logger.info(f"✅ Cookie 文件上传成功: {cookie_file_path}")
            return jsonify({
                "code": 200,
                "msg": "Cookie 文件上传成功",
                "data": None
            }), 200
        except Exception as e:
            logger.error(f"上传 Cookie 文件失败: {str(e)}")
            return jsonify({
                "code": 500,
                "msg": f"上传 Cookie 文件失败: {str(e)}",
                "data": None
            }), 500

    @account_bp.route('/accounts/cookie/download', methods=['GET'])
    def download_cookie():
        """下载 Cookie 文件"""
        try:
            file_path = request.args.get('filePath')
            if not file_path:
                return jsonify({
                    "code": 500,
                    "msg": "缺少文件路径参数",
                    "data": None
                }), 400
            
            # 验证文件路径安全性
            cookie_file_path = (COOKIES_DIR / file_path).resolve()
            base_path = COOKIES_DIR.resolve()
            
            if not str(cookie_file_path).startswith(str(base_path)):
                return jsonify({
                    "code": 500,
                    "msg": "非法文件路径",
                    "data": None
                }), 400
            
            if not cookie_file_path.exists():
                return jsonify({
                    "code": 500,
                    "msg": "Cookie 文件不存在",
                    "data": None
                }), 404
            
            return send_from_directory(
                directory=str(cookie_file_path.parent),
                path=cookie_file_path.name,
                as_attachment=True
            )
        except Exception as e:
            logger.error(f"下载 Cookie 文件失败: {str(e)}")
            return jsonify({
                "code": 500,
                "msg": f"下载 Cookie 文件失败: {str(e)}",
                "data": None
            }), 500

    return account_bp


def run_async_function(type_val, account_id, status_queue):
    """在线程中运行异步登录函数"""
    match type_val:
        case '1':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(xiaohongshu_cookie_gen(account_id, status_queue))
            loop.close()
        case '2':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_tencent_cookie(account_id, status_queue))
            loop.close()
        case '3':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(douyin_cookie_gen(account_id, status_queue))
            loop.close()
        case '4':
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_ks_cookie(account_id, status_queue))
            loop.close()


def sse_stream(status_queue):
    """SSE 流生成器"""
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
        else:
            time.sleep(0.1)
