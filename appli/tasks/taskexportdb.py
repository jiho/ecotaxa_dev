# -*- coding: utf-8 -*-
from appli import db,app, database , ObjectToStr,PrintInCharte,gvp,gvg,EncodeEqualList,DecodeEqualList
from flask import Blueprint, render_template, g, flash,request
import logging,os,csv,re,zlib
import zipfile,psycopg2.extras
from time import time
from pathlib import Path
from zipfile import ZipFile
from flask.ext.login import current_user
from appli.tasks.taskmanager import AsyncTask,DoTaskClean
from appli.database import GetAll,ExecSQL,GetDBToolsDir

table_list=("taxonomy","users","roles","users_roles"
            ,"projects","projectspriv","process","acquisitions","samples"
            ,"objects","images","objectsclassifhisto","alembic_version")

class TaskExportDb(AsyncTask):
    class Params (AsyncTask.Params):
        def __init__(self,InitStr=None):
            self.steperrors=[]
            super().__init__(InitStr)
            if InitStr==None: # Valeurs par defaut ou vide pour init
                self.ProjectId=()


    def __init__(self,task=None):
        super().__init__(task)
        if task==None:
            self.param=self.Params()
        else:
            self.param=self.Params(task.inputparam)

    def SPCommon(self):
        logging.info("Execute SPCommon for DB Export")
        self.pgcur=db.engine.raw_connection().cursor(cursor_factory=psycopg2.extras.DictCursor)



    def SPStep1(self):
        logging.info("Input Param = %s"%(self.param.__dict__))
        logging.info("Current directory = %s"%os.getcwd())
        # Note liste des tables
        # select ns.oid oidns, ns.nspname, c.relname,c.oid reloid
        # from pg_namespace ns
        # join pg_class c on  relnamespace=ns.oid
        #   where ns.nspname='public' and relkind='r'

        # table_list=("users",) # pour test permet d'exporter moins de données
        toolsdir=GetDBToolsDir()
        cmd=os.path.join( toolsdir,"pg_dump")

        cmd+=" -h "+app.config['DB_HOST']+" -U "+app.config['DB_USER']+" -w "   #+" -W "+app.config['DB_PASSWORD']
        # -s = le schema , -F le format -f le fichier
        cmd+="  --schema-only --format=p  -f schema.sql -E LATIN1 -n public --no-owner  --no-privileges --no-security-labels --no-tablespaces  "+app.config['DB_DATABASE']+"  >dumpschemaout.txt"
        logging.info("Export Schema : %s",cmd)
        os.system(cmd)
        zfile=ZipFile('ecotaxadb.zip', 'w',allowZip64 = True,compression= zipfile.ZIP_DEFLATED)
        zfile.write('schema.sql')
        for t in table_list:
            ColList=GetAll("""select a.attname from pg_namespace ns
                              join pg_class c on  relnamespace=ns.oid
                              join pg_attribute a on a.attrelid=c.oid
                              where ns.nspname='public' and relkind='r' and a.attname not like '%.%'
                              and attnum>0  and c.relname='{0}'  order by attnum""".format(t))

            logging.info("Save table %s"%t)
            with open("temp.copy","w",encoding='latin_1') as f:
                query="select %s from %s t"%(",".join(["t."+x[0] for x in ColList]),t)
                if t in ('projects','projectspriv',"process","acquisitions","samples","objects"):
                    query+=" where projid in (%s)"%(self.param.ProjectId,)
                if t in ('objectsclassifhisto','images'):
                    query+=" join objects o on o.objid=t.objid where o.projid in (%s)"%(self.param.ProjectId,)
                self.pgcur.copy_to(f,"("+query+")")
            zfile.write("temp.copy",arcname=t+".copy")
        logging.info("Save Images")
        vaultroot=Path("../../vault")
        self.pgcur.execute("select imgid,file_name,thumb_file_name from images i join objects o on o.objid=i.objid where o.projid in (%s)"%(self.param.ProjectId,))
        for r in self.pgcur:
            if r[1]:
                zfile.write(vaultroot.joinpath(r[1]).as_posix(),arcname="images/%s.img"%r[0])
            if r[2]:
                zfile.write(vaultroot.joinpath(r[2]).as_posix(),arcname="images/%s.thumb"%r[0])

        zfile.close()
        self.task.taskstate="Done"
        self.UpdateProgress(100,"Export successfull")

        # self.task.taskstate="Error"
        # self.UpdateProgress(10,"Test Error")


    def QuestionProcess(self):
        if not current_user.has_role(database.AdministratorLabel):
            return PrintInCharte("ACCESS DENIED for this feature, Admin Required")
        txt="<h3>Database export Task creation</h3>"
        errors=[]
        if self.task.taskstep==0:
            # Le projet de base est choisi second écran ou validation du second ecran
            if gvp('starttask')=="Y":
                # validation du second ecran
                self.param.ProjectId=",".join( (x[4:] for x in request.form if x[0:4]=="prj_") )

                # Verifier la coherence des données
                # errors.append("TEST ERROR")
                if self.param.ProjectId=='' : errors.append("You must select at least one project")
                if len(errors)>0:
                    for e in errors:
                        flash(e,"error")
                else: # Pas d'erreur, on lance la tache
                    return self.StartTask(self.param)
            else: # valeurs par default
                pass
            #recupere les projets
            sql="""select projid,title,status
                    from projects
                    order by lower(title)"""
            PrjList=GetAll(sql,cursor_factory=None)
            txt+="""
            <form method=post action=?>
            <input type=hidden name=starttask value=Y>

            Select <a name="tbltop" href="#tbltop" onclick="$('#TblPrj input').prop( 'checked', true )">All</a> /
             <a href="#tbltop" onclick="$('#TblPrj input').prop( 'checked', false );">None</a>
            <table id=TblPrj class='table table-condensed table-bordered' style='width:600px;'>"""
            for r in PrjList:
                txt+="<tr><td><input type=checkbox name=prj_{0}>{0}</td><td>{1}</td><td>{2}</td></tr>".format(*r)
            txt+="""</table>
            <input type=submit class='btn btn-primary' value='Start Database Export'>
            </form>
            """;
            return PrintInCharte(txt);



    def GetResultFile(self):
        return 'ecotaxadb.zip'