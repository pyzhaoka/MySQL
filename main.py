import os
import sys
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, 
                            QVBoxLayout, QWidget, QLineEdit, QLabel, QPushButton, 
                            QHBoxLayout, QMessageBox, QFileDialog, QMenu, QAction)
from PyQt5.QtCore import Qt
import mysql.connector
from mysql.connector import Error

class MySQLBackupTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MySQL 备份与还原工具")
        self.setGeometry(100, 100, 800, 600)
        
        # 数据库连接变量
        self.connection = None
        self.current_db = None
        
        # 初始化UI
        self.init_ui()
        
    def resource_path(self, relative_path):
        """获取资源的绝对路径（兼容开发模式和打包模式）"""
        try:
            base_path = sys._MEIPASS  # PyInstaller临时文件夹
        except AttributeError:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def find_mysql_tool(self, tool_name):
        """智能查找MySQL工具"""
        # 1. 检查打包后的资源路径
        tool_path = self.resource_path(f"mysql/bin/{tool_name}.exe")
        if os.path.exists(tool_path):
            return tool_path
            
        # 2. 检查程序所在目录
        local_path = os.path.join(os.path.dirname(sys.executable), "mysql", "bin", f"{tool_name}.exe")
        if os.path.exists(local_path):
            return local_path
            
        # 3. 检查系统PATH
        try:
            subprocess.run([tool_name, "--version"], 
                          check=True, 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW)
            return tool_name
        except:
            pass
            
        # 如果都找不到，显示友好错误
        QMessageBox.critical(
            self, 
            "错误", 
            f"未找到 {tool_name}.exe\n\n"
            "解决方案：\n"
            "1. 请将mysql/bin目录放在程序同级目录下\n"
            "2. 或者将MySQL工具添加到系统PATH"
        )
        return None
        
    def init_ui(self):
        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # 连接设置区域
        connection_group = QWidget()
        connection_layout = QHBoxLayout()
        connection_group.setLayout(connection_layout)
        
        # 服务器地址
        self.host_input = QLineEdit("localhost")
        connection_layout.addWidget(QLabel("服务器:"))
        connection_layout.addWidget(self.host_input)
        
        # 端口
        self.port_input = QLineEdit("3306")
        connection_layout.addWidget(QLabel("端口:"))
        connection_layout.addWidget(self.port_input)
        
        # 用户名
        self.user_input = QLineEdit("root")
        connection_layout.addWidget(QLabel("用户名:"))
        connection_layout.addWidget(self.user_input)
        
        # 密码
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        connection_layout.addWidget(QLabel("密码:"))
        connection_layout.addWidget(self.password_input)
        
        # 连接按钮
        self.connect_button = QPushButton("连接 MySQL")
        self.connect_button.clicked.connect(self.connect_to_mysql)
        connection_layout.addWidget(self.connect_button)
        
        layout.addWidget(connection_group)
        
        # 数据库树形视图
        self.db_tree = QTreeWidget()
        self.db_tree.setHeaderLabel("数据库")
        self.db_tree.itemClicked.connect(self.on_db_selected)
        self.db_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.db_tree.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.db_tree)
        
        # 状态栏
        self.statusBar().showMessage("准备就绪")
    
    def connect_to_mysql(self):
        host = self.host_input.text()
        port = self.port_input.text()
        user = self.user_input.text()
        password = self.password_input.text()
        
        try:
            # 尝试连接MySQL服务器
            self.connection = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password
            )
            
            if self.connection.is_connected():
                self.statusBar().showMessage(f"成功连接到 MySQL 服务器: {host}")
                self.load_databases()
                self.connect_button.setEnabled(False)
        except Error as e:
            QMessageBox.critical(self, "连接错误", f"无法连接到 MySQL 服务器:\n{str(e)}")
            self.statusBar().showMessage("连接失败")
    
    def load_databases(self):
        """加载数据库列表"""
        self.db_tree.clear()
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            
            for (db_name,) in databases:
                if db_name not in ['information_schema', 'mysql', 'performance_schema', 'sys']:
                    item = QTreeWidgetItem(self.db_tree)
                    item.setText(0, db_name)
                    item.setData(0, Qt.UserRole, db_name)
            
            cursor.close()
        except Error as e:
            QMessageBox.critical(self, "错误", f"无法获取数据库列表:\n{str(e)}")
    
    def on_db_selected(self, item):
        """数据库被选中时的处理"""
        self.current_db = item.text(0)
        self.statusBar().showMessage(f"已选择数据库: {self.current_db}")
    
    def show_context_menu(self, position):
        """显示右键菜单"""
        item = self.db_tree.itemAt(position)
        if not item:
            return
            
        self.current_db = item.text(0)
        
        menu = QMenu()
        
        backup_action = QAction("备份数据库", self)
        backup_action.triggered.connect(self.backup_database)
        menu.addAction(backup_action)
        
        restore_action = QAction("还原数据库", self)
        restore_action.triggered.connect(self.restore_database)
        menu.addAction(restore_action)
        
        menu.exec_(self.db_tree.viewport().mapToGlobal(position))
    
    def backup_database(self):
        """备份选定的数据库"""
        if not self.current_db:
            QMessageBox.warning(self, "警告", "请先选择一个数据库")
            return
            
        # 获取保存位置
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(
            self, 
            "保存备份文件", 
            f"{self.current_db}.sql", 
            "SQL Files (*.sql);;All Files (*)", 
            options=options
        )
        
        if not file_name:
            return
            
        try:
            # 使用 mysqldump 命令备份数据库
            host = self.host_input.text()
            port = self.port_input.text()
            user = self.user_input.text()
            password = self.password_input.text()
            
            mysqldump_path = self.find_mysql_tool("mysqldump")
            if not mysqldump_path:
                return
                
            command = [
                mysqldump_path,
                f'-h{host}',
                f'-P{port}',
                f'-u{user}',
                f'-p{password}',
                '--routines',
                '--triggers',
                '--events',
                self.current_db
            ]
            
            with open(file_name, 'w') as output_file:
                process = subprocess.Popen(
                    command, 
                    stdout=output_file, 
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                _, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise Exception(stderr.decode('utf-8', errors='ignore'))
                
            QMessageBox.information(self, "成功", f"数据库 {self.current_db} 已成功备份到:\n{file_name}")
            self.statusBar().showMessage(f"备份完成: {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "备份失败", f"备份过程中出现错误:\n{str(e)}")
            self.statusBar().showMessage("备份失败")
    
    def restore_database(self):
        """还原数据库"""
        if not self.current_db:
            QMessageBox.warning(self, "警告", "请先选择一个数据库")
            return
            
        # 获取备份文件
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "选择备份文件", 
            "", 
            "SQL Files (*.sql);;All Files (*)", 
            options=options
        )
        
        if not file_name:
            return
            
        # 确认对话框
        reply = QMessageBox.question(
            self, 
            "确认还原", 
            f"确定要将数据库 {self.current_db} 还原为备份文件 {file_name} 的内容吗?\n此操作将覆盖现有数据!", 
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
            
        try:
            # 使用 mysql 命令还原数据库
            host = self.host_input.text()
            port = self.port_input.text()
            user = self.user_input.text()
            password = self.password_input.text()
            
            mysql_path = self.find_mysql_tool("mysql")
            if not mysql_path:
                return
                
            command = [
                mysql_path,
                f'-h{host}',
                f'-P{port}',
                f'-u{user}',
                f'-p{password}',
                self.current_db
            ]
            
            with open(file_name, 'r') as input_file:
                process = subprocess.Popen(
                    command, 
                    stdin=input_file, 
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                _, stderr = process.communicate()
                
                if process.returncode != 0:
                    raise Exception(stderr.decode('utf-8', errors='ignore'))
                
            QMessageBox.information(self, "成功", f"数据库 {self.current_db} 已成功从备份文件 {file_name} 还原")
            self.statusBar().showMessage(f"还原完成: {file_name}")
        except Exception as e:
            QMessageBox.critical(self, "还原失败", f"还原过程中出现错误:\n{str(e)}")
            self.statusBar().showMessage("还原失败")
    
    def closeEvent(self, event):
        """关闭窗口时断开数据库连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
        event.accept()

if __name__ == "__main__":
    # Windows 7兼容模式
    if sys.platform == "win32":
        os.environ["PYTHONLEGACYWINDOWSSTDIO"] = "1"
    
    app = QApplication(sys.argv)
    window = MySQLBackupTool()
    window.show()
    sys.exit(app.exec_())