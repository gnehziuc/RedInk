# -*- coding: utf-8 -*-
"""
发布相关 API 路由

提供小红书图文发布接口
"""
import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread
from flask import Blueprint, request, jsonify

from backend.services.xhs_publisher import publish_image_post

logger = logging.getLogger(__name__)

# 存储发布任务状态
publish_tasks = {}


def create_publish_blueprint():
    """创建发布路由蓝图"""
    publish_bp = Blueprint('publish', __name__, url_prefix='/publish')
    
    @publish_bp.route('/xhs/image', methods=['POST'])
    def publish_xhs_image():
        """
        发布小红书图文笔记
        
        请求体:
        {
            "account_id": 1,
            "title": "标题",
            "content": "正文内容",
            "image_paths": ["path/to/image1.jpg", "path/to/image2.jpg"],
            "tags": ["话题1", "话题2"],
            "publish_date": "2024-01-20 10:00"  // 可选，定时发布
        }
        """
        try:
            data = request.get_json()
            
            # 验证必填字段
            account_id = data.get('account_id')
            title = data.get('title', '')
            content = data.get('content', '')
            image_paths = data.get('image_paths', [])
            tags = data.get('tags', [])
            publish_date_str = data.get('publish_date')
            
            if not account_id:
                return jsonify({
                    "code": 400,
                    "msg": "缺少账号 ID",
                    "data": None
                }), 400
            
            if not image_paths:
                return jsonify({
                    "code": 400,
                    "msg": "缺少图片路径",
                    "data": None
                }), 400
            
            if not title:
                return jsonify({
                    "code": 400,
                    "msg": "缺少标题",
                    "data": None
                }), 400
            
            # 解析定时发布时间
            publish_date = None
            if publish_date_str:
                try:
                    publish_date = datetime.strptime(publish_date_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    return jsonify({
                        "code": 400,
                        "msg": "定时发布时间格式错误，请使用 YYYY-MM-DD HH:MM",
                        "data": None
                    }), 400
            
            # 创建任务 ID
            task_id = str(uuid.uuid4())
            publish_tasks[task_id] = {
                "status": "pending",
                "message": "任务已创建，等待执行",
                "created_at": datetime.now().isoformat()
            }
            
            # 在后台线程中执行发布
            def run_publish():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    publish_tasks[task_id]["status"] = "running"
                    publish_tasks[task_id]["message"] = "正在发布..."
                    
                    result = loop.run_until_complete(
                        publish_image_post(
                            account_id=account_id,
                            title=title,
                            content=content,
                            image_paths=image_paths,
                            tags=tags,
                            publish_date=publish_date
                        )
                    )
                    
                    if result["success"]:
                        publish_tasks[task_id]["status"] = "success"
                        publish_tasks[task_id]["message"] = result["message"]
                        publish_tasks[task_id]["note_id"] = result.get("note_id")
                    else:
                        publish_tasks[task_id]["status"] = "failed"
                        publish_tasks[task_id]["message"] = result["message"]
                        
                except Exception as e:
                    logger.error(f"发布任务执行失败: {e}")
                    publish_tasks[task_id]["status"] = "failed"
                    publish_tasks[task_id]["message"] = str(e)
                finally:
                    loop.close()
                    publish_tasks[task_id]["completed_at"] = datetime.now().isoformat()
            
            thread = Thread(target=run_publish, daemon=True)
            thread.start()
            
            logger.info(f"✅ 发布任务已创建: {task_id}")
            return jsonify({
                "code": 200,
                "msg": "发布任务已创建",
                "data": {
                    "task_id": task_id
                }
            }), 200
            
        except Exception as e:
            logger.error(f"创建发布任务失败: {e}")
            return jsonify({
                "code": 500,
                "msg": f"创建发布任务失败: {str(e)}",
                "data": None
            }), 500
    
    @publish_bp.route('/xhs/status/<task_id>', methods=['GET'])
    def get_publish_status(task_id):
        """获取发布任务状态"""
        if task_id not in publish_tasks:
            return jsonify({
                "code": 404,
                "msg": "任务不存在",
                "data": None
            }), 404
        
        task = publish_tasks[task_id]
        return jsonify({
            "code": 200,
            "msg": None,
            "data": {
                "task_id": task_id,
                "status": task["status"],
                "message": task["message"],
                "created_at": task.get("created_at"),
                "completed_at": task.get("completed_at"),
                "note_id": task.get("note_id")
            }
        }), 200
    
    @publish_bp.route('/xhs/tasks', methods=['GET'])
    def list_publish_tasks():
        """获取所有发布任务列表"""
        tasks_list = []
        for task_id, task in publish_tasks.items():
            tasks_list.append({
                "task_id": task_id,
                "status": task["status"],
                "message": task["message"],
                "created_at": task.get("created_at"),
                "completed_at": task.get("completed_at")
            })
        
        # 按创建时间倒序排列
        tasks_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return jsonify({
            "code": 200,
            "msg": None,
            "data": tasks_list
        }), 200
    
    return publish_bp
