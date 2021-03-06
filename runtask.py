# -*- coding: utf-8 -*-
# This file is part of Ecotaxa, see license.md in the application root directory for license informations.
# Copyright (C) 2015-2016  Picheral, Colin, Irisson (UPMC-CNRS)
from appli import db,app, g
from appli.tasks.taskmanager import AsyncTask,LoadTask
import logging,sys,os


if __name__ == '__main__':
    task = None
    taskid=-9999
    try:
        # print("%s %s"%(sys.argv,len(sys.argv)))
        # print(os.getcwd())
        # On verifie qu'il y a au moins un parametre, c'est le taskid
        if len(sys.argv)==1:
            raise Exception ("Parameter Missing, Task ID required :")
        taskid=int(sys.argv[1])
        # taskid=1
        # On se place dans le repertoire de travail
        workingdir=os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "temptask/task%06d"%(int(taskid))))
        os.chdir(workingdir)
        # On active le logger
        LoggingFormat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(filename='TaskLog.txt',level=logging.DEBUG,format=LoggingFormat)
        logging_console = logging.StreamHandler()
        logging_console.setLevel(logging.DEBUG)
        logging_console.setFormatter(logging.Formatter(LoggingFormat))
        logging.getLogger('').addHandler(logging_console)
        with app.app_context(): # Création d'un contexte pour utiliser les fonction GetAll,ExecSQL qui mémorisent
            g.db=None
            # logging.warning("Test Warning")
            # raise Exception("TEST")
            # On crée la tache à partir de la base
            task=LoadTask(taskid)
            task.task.taskstate="Running"
            # on execute SPCommon s'il existe
            fct=getattr(task,"SPCommon",None)
            if fct!=None:
                fct()
            # on execute le code du step associé
            fctname="SPStep"+str(task.task.taskstep)
            fct=getattr(task,fctname,None)
            if fct==None:
                raise Exception ("Procedure Missing :"+fctname)
            fct()
    except:
        db.session.rollback()
        db.engine.begin()
        if task is not None:
            task = LoadTask(taskid)
            task.task.taskstate="Error"
            task.task.progresspct=-1
            task.task.progressmsg="Unhandled SubProcess Exception : "+str(sys.exc_info())
            db.session.commit()
        logging.exception("Unhandled SubProcess Exception")

