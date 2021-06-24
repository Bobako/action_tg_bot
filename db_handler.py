import sqlalchemy
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from copy import copy
import os

Base = declarative_base()

REQUEST_INCOMPLETE_STATUS = "Создается.."
REQUEST_NOT_MODERATED_STATUS = "Не проверен"
REQUEST_MODERATED_STATUS = "Проверен, запрос принят"
BAD_REQUEST_MODERATED_STATUS = "Отклонен"


class Request(Base):
    __tablename__ = 'requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    user_contact = Column(String)
    user_name = Column(String)
    photo_path = Column(String)
    receipt_id = Column(String)
    request_status = Column(String)
    user_link = Column(String)

    def __init__(self, user_id=None, photo_path=None, receipt_id=None, request_status=None, user_contact=None,
                 user_name=None, user_link=None):
        self.user_id = user_id
        self.user_link = user_link
        self.photo_path = photo_path
        self.receipt_id = receipt_id
        self.request_status = request_status
        self.user_contact = user_contact
        self.user_name = user_name

    def __repr__(self):
        return f" {self.user_link} {self.user_contact} {self.user_name} {self.photo_path} {self.receipt_id}" \
               f" {self.request_status}"


engine = sqlalchemy.create_engine('sqlite:///requests.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def validate_number(number):
    if number is None:
        return True
    session = Session()
    if session.query(Request).filter(Request.receipt_id == int(number)).first():
        session.close()
        return False
    else:
        session.close()
        return True


def add_request(user_id, user_link, photo_path, receipt_id):
    new_request = Request(user_id=user_id, photo_path=photo_path, receipt_id=receipt_id,
                          request_status=REQUEST_INCOMPLETE_STATUS, user_link=user_link)
    session = Session()
    session.add(new_request)
    session.commit()


def update_request(user_id, request_id=None, **kwargs):
    keys = kwargs.keys()
    session = Session()
    if request_id:
        request = session.query(Request).filter(Request.id == request_id).one()
    else:
        request = session.query(Request).filter(Request.user_id == user_id)[-1]
    for key in keys:
        if key == 'user_contact':
            request.user_contact = kwargs[key]
        elif key == 'user_name':
            request.user_name = kwargs[key]
        elif key == 'request_status':
            request.request_status = kwargs[key]

    session.commit()


def remove_incomplete_requests():
    session = Session()
    for request in session.query(Request).filter(
            Request.request_status == REQUEST_INCOMPLETE_STATUS):
        session.delete(request)
    session.commit()


def get_not_validated_request():
    session = Session()
    request = session.query(Request).filter(Request.request_status == REQUEST_NOT_MODERATED_STATUS).first()
    if request:
        request_id, photo_path, receipt_id = request.id, request.photo_path, request.receipt_id
        session.close()
        return request_id, photo_path, receipt_id
    session.close()
    return None, None, None


def get_existing_user_info(user_id):
    session = Session()
    request = session.query(Request).filter(Request.user_id == user_id).first()
    if request.user_contact and request.user_name:
        info = request.user_name, request.user_contact
    else:
        info = None
    session.close()
    return info


def get_valid_by_request_id(request_id):
    session = Session()
    request = session.query(Request).filter(Request.id == request_id).one()
    user = request.user_id
    valid = request.request_status
    session.close()
    return user, valid


if __name__ == "__main__":
    print(get_not_validated_request())
    for instance in Session().query(Request).order_by(Request.id):
        print(instance)
