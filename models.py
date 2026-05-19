from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)          # = project_id
    title = db.Column(db.String(500))
    url = db.Column(db.String(300))
    description = db.Column(db.Text)
    cost = db.Column(db.String(100))
    category = db.Column(db.String(200))
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'description': self.description[:200] + '…',
            'cost': self.cost,
            'category': self.category,
            'published_at': self.published_at.strftime('%Y-%m-%d %H:%M') if self.published_at else '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M')
        }