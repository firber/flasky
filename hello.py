import os
from threading import Thread
from flask import Flask, render_template, session, redirect, url_for
from flask_script import Manager, Shell
from flask_bootstrap import Bootstrap
from flask_moment import Moment
from flask_wtf import Form
from wtforms import StringField, SubmitField
from wtforms.validators import Required
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_mail import Mail, Message
#将该文件所在目录作为根目录 basedir
basedir = os.path.abspath(os.path.dirname(__file__))

#创建一个Flask类的对象，作为一个程序实例，用以处理接收自Web客户端的所有请求
app = Flask(__name__)   #该过程所接收的参数为该程序主模块或包的名字，Flask用这个参数确定程序的根目录
# Flask.config 字典可用来存储框架、扩展和程序本身的配置变量，可以从文件或环境中导入配置值，具体见http://docs.jinkan.org/docs/flask/config.html
app.config['SECRET_KEY'] = 'hard to guess string'    #配置密钥，密钥一般推荐保存在环境变量中
app.config['SQLALCHEMY_DATABASE_URI'] =\           #在行末尾加上反斜线（\），表示在下一行继续输入，语句跨行  
    'sqlite:///' + os.path.join(basedir, 'data.sqlite')   # SQLALCHEMY_DATABASE_URI 就是用来保存程序使用的数据库URL，此处将数据库设在根目录下
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True        #该值为 True,则每次请求结束后都会自动提交数据库中的改动
app.config['MAIL_SERVER'] = 'smtp.163.com'      
app.config['MAIL_PORT'] = 25           
app.config['MAIL_USE_TLS'] = True       #启动 Transport Layer Security 协议
# 从环境变量接收邮件账户和密码
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')   
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
# 设置发送电子邮件的具体参数
app.config['FLASKY_MAIL_SUBJECT_PREFIX'] = '[Flasky]'  #定义邮件主题的前缀
app.config['FLASKY_MAIL_SENDER'] = 'Flasky Admin <flasky@example.com>' #定义邮件发件人的地址
app.config['FLASKY_ADMIN'] = os.environ.get('FLASKY_ADMIN')   #从环境变量接收电子邮件的收件人

manager = Manager(app)  #初始化命令行扩展 Flask-Script
bootstrap = Bootstrap(app)
moment = Moment(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
mail = Mail(app)


# 定义数据库中的 Role 模型
class Role(db.Model):
    __tablename__ = 'roles'  #定义模型在数据库中使用的表名
	# db.Column 定义数据库列的类型和属性
    id = db.Column(db.Integer, primary_key=True)  # 整型的id通常为模型的主键
    name = db.Column(db.String(64), unique=True)  
    users = db.relationship('User', backref='role', lazy='dynamic')  #users属性对应与角色相关联的用户列表

    def __repr__(self):
        return '<Role %r>' % self.name

# 定义数据库中的 User 模型
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    def __repr__(self):
        return '<User %r>' % self.username


def send_async_email(app, msg):
    with app.app_context():  # 获得当前app的程序上下文--with语句
        mail.send(msg)

# 异步电子邮件发送功能
def send_email(to, subject, template, **kwargs):
    msg = Message(app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
                  sender=app.config['FLASKY_MAIL_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr

# 定义继承自Form的Web表单类
class NameForm(Form):
    name = StringField('What is your name?', validators=[Required()])
    submit = SubmitField('Submit')

# 集成 Python Shell
def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role)
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500


@app.route('/', methods=['GET', 'POST'])
def index():
    form = NameForm()
    if form.validate_on_submit():   #表单提交的数据被验证函数通过
        user = User.query.filter_by(username=form.name.data).first() #查询数据库中是否已经存在表单提交的用户名
        if user is None:   #若表单提交的用户名为数据库中不存在的
            user = User(username=form.name.data)  #创建该用户
            db.session.add(user)   #将用户信息添加到数据库会话中
            session['known'] = False   #使用 known 参数将该用户标记为“未知的新用户”
            if app.config['FLASKY_ADMIN']:  #将新用户的信息发送到管理员邮箱
                send_email(app.config['FLASKY_ADMIN'], 'New User',
                           'mail/new_user', user=user)
        else:
            session['known'] = True  #使用 known 参数将该用户标记为“已有老用户”
        session['name'] = form.name.data  #将表单提交的数据保存至会话中
        return redirect(url_for('index'))  #重定向
    return render_template('index.html', form=form, name=session.get('name'),
                           known=session.get('known', False))


if __name__ == '__main__':
    manager.run()
