from app import db, login, app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import jwt
from time import time



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    name = db.Column(db.String(64))
    surname = db.Column(db.String(64))
    password_hash = db.Column(db.String(128))
    _series = db.Column(db.Text())

    def __repr__(self):
        return f"Username : {self.username}, Name : {self.name}, Surname : {self.surname}, Email : {self.email}," \
               f" Series : {self.series}"

    def _set_series(self, *args):
        return print("Use .add_serie method instead")

    def _get_series(self):
        return self._series

    series = property(_get_series,_set_series)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def list_serie(self):
        # Le format du texte est sous la forme {idserie}x{Snum_saisonEnum_episode}-{idserie}x{Snum_saisonEnum_episode} .
        # Renvoie une liste de couple (id serie, Snum_saisonEnum_episode)
        if self.series is not None :
            serie_episode_list = self.series.split('-')
            serie_list = []
            for serie_episode in serie_episode_list:
                serie_list.append((serie_episode.split('x')[0],serie_episode.split('x')[1]))
            return serie_list
        else :
            return "The user doesn't have any series"

    def is_in_series(self,id):
        return(str(id) in self.series)

    def add_serie(self, id_serie):
        if self.series is None or self.series == '':
            self._series = f"{id_serie}xS1E1"
        else:
            self._series += f"-{id_serie}xS1E1"
        db.session.commit()

    def remove_serie(self,id_serie):
        string_series = self._series.split('-')
        for i, string_serie in enumerate(string_series):
            split_serie = string_serie.split('x')
            if split_serie[0] == str(id_serie):
                if i == 0 :
                    self._series = self._series.replace(string_serie+'-','')
                else :
                    self._series = self._series.replace('-'+string_serie,'')
                print(self._series)
        db.session.commit()

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)


@login.user_loader
def user_loader(id):
    return User.query.get(int(id))

