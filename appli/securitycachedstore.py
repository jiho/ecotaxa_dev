from flask.ext.security import SQLAlchemyUserDatastore

import werkzeug.contrib.cache
import threading

# Ce datastore permet de mettre en cache les utilisateurs
class SQLAlchemyUserDatastoreCACHED (SQLAlchemyUserDatastore):
    """ Version integrant un cache du Datastore
    """
    def __init__(self, db, user_model, role_model):
        # print("******************* SQLAlchemyUserDatastoreCACHED INIT  ********************* ")
        SQLAlchemyUserDatastore.__init__(self, db, user_model, role_model)
        self.cache_users = werkzeug.contrib.cache.SimpleCache(threshold=500, default_timeout=300) # 5 minutes
        self.lock = threading.Lock()  # on compense que simple cache n'est pas thread safe

    def get_user(self, identifier):
        #A Chaque login on cleanne le cache, ca permet d'avoir un effet immediat sur les modification en base
        with self.lock:
            self.cache_users.clear()
        return super().get_user(identifier)

    def find_user(self, **kwargs):
        # print("******************* find_user  ********************* %s"%kwargs)
        with self.lock:
            u=self.cache_users.get(kwargs["id"])
            if u is None:
                u=self.user_model.query.filter_by(**kwargs).first()
                tmprole=u.roles # used to force quering Database
                self.cache_users.set(kwargs["id"],u)
            return u

