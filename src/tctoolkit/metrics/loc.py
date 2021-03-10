import sys,os,io
import string, sqlite3
import pandas as pd
from optparse import OptionParser
from datetime import datetime
from pygments.token import Comment,Token
from pygments.lexers import get_lexer_by_name
import codecs, traceback
from pathlib import Path
sys.path.append("..")
from tctoolkitutil import DirFileLister
class Hierarchy():
    def __init__(self,parent=None):
        self.parent = parent
        self.cchild = 0
        self.stack = []
        self.depth = 0
        self.count = 0
        self.ccount = 0
        self.depth_line=0
        
class Countlines():
    
    def __init__(self, language, dependspath=[]):
        dependencypath = dependspath
        self.language = language
        self.srcdir = None
        self.lexer = get_lexer_by_name(language)
        self.openlist = ["for","while","if","else","loop","until"]
        self.closelist = ['}', "end"]
        self.conn = sqlite3.connect("analysis.db")
        self.c = self.conn.cursor()
        self.check=0

    def StripAtStart(self,src, strtostrip):
        if(src.startswith(strtostrip)):
            src = src[len(strtostrip):]
        return (src)
        
    def getFiles(self, srcdir):
        self.srcdir = srcdir
        if(self.srcdir.endswith(os.sep) == False):
            self.srcdir += os.sep
        filelister = DirFileLister(self.srcdir)
        filelist = filelister.getFilesForLang(self.language)
        return filelist

    def run(self,srcdir):
        filelist = self.getFiles(srcdir)
        check=True
        print('Choose from this:\n\t1.loc\n\t2.Blockdepth')
        if int(input())==2:check=False
        # database
        if check:
            self.c.execute(""" CREATE TABLE IF NOT EXISTS Files
            (Checkpoint_name text,FILENAME text PRIMARY KEY,DATE text,src_loc integer,total_loc integer,comment integer,
            FOREIGN KEY (Checkpoint_name) REFERENCES Checkpoint (Checkpoint_name))""")
        else:
            self.c.execute('''CREATE TABLE IF NOT EXISTS Blockdepth
            (Checkpoint_name text,FILENAME text,Parent text,Function text,Max_depth integer,dept_line integer,loc integer, 
            FOREIGN KEY (FILENAME) REFERENCES Files (FILENAME),FOREIGN KEY (Checkpoint_name) REFERENCES Checkpoint (Checkpoint_name),
            UNIQUE(Filename,Parent,Function))''' )
        self.conn.commit()
        for srcfile in filelist:
            if check:
                a = self.Readfile(srcfile)
                try:
                    self.c.execute('''INSERT INTO Files VALUES(?,?,?,?,?,?)''',
                    (self.check,str(Path(srcfile).absolute()),datetime.now(),a[0],a[1],a[2]))
                    self.conn.commit()
                except:pass
            else:
                self.Blockdept(srcfile)
        # print(pd.read_sql_query("SELECT * FROM Files", self.conn))
        # print (pd.read_sql_query("SELECT * FROM Blockdepth", self.conn))

        
    def Blockdept(self, srcfile):
        type1 = ['c', 'cpp', 'java', 'js','cs']
        type2 = ['rb', 'py']
        if self.StripAtStart(srcfile,self.srcdir).split('.')[1] in type1:
            return self.Type1(srcfile)
        else:
            return self.Type2(srcfile)

    def Type1(self, srcfile):
        function = []
        a = []
        startcal, count = 0, 0
        gotfunc = False
        with codecs.open(srcfile, "rb", encoding='utf-8', errors='ignore') as code:
            for ttype, value in self.lexer.get_tokens(code.read()):
                if '\n' in value:count+=1
                if gotfunc:
                    if value == '{':
                        startcal += 1
                        gotfunc = False
                    elif value == ';':
                        gotfunc = False
                        function.pop()
                        a[-1].count = 0
                        a.pop()
                    else: continue
                dummy,a,function,gotfunc=self.Checkfunc(ttype,value,gotfunc,startcal,a,function,count+1)
                if not dummy and a and len(a[-1].stack) == 0 and a[-1].depth > 0:
                    self.insertval(srcfile,a,function)
                    startcal -= 1
                    function.pop()
                    a.pop()

    def Checkfunc(self,ttype,value,gotfunc,startcal,a,function,count):
        if ttype == Token.Name.Function :
            gotfunc = True
            if startcal:    
                obj = Hierarchy(function[-1])
            else:
                obj = Hierarchy()
            a.append(obj)
            function.append(value)
            a[-1].count += 1
            return 1,a,function,gotfunc
        if '{' == value and startcal:
            a[-1].stack.append(1)
            a[-1].depth_line=count
            a[-1].depth = max(a[-1].depth, len(a[-1].stack))
        if '}'==value and startcal:
            a[-1].stack.pop()
        if startcal and '\n' in value:
            a[-1].count += 1
        return 0,a,function,gotfunc

    def insertval(self,srcfile,a,function):
        if a[-1].parent:
            a[-2].cchild = a[-1].depth
            a[-2].ccount = a[-1].count
        self.c.execute('''INSERT INTO Blockdepth VALUES(?,?,?,?,?,?,?)''',
        (self.check,str(Path(srcfile).absolute()),a[-1].parent,function[-1],a[-1].cchild+a[-1].depth,a[-1].depth_line,a[-1].count+a[-1].ccount))
        self.conn.commit()

    def Type2(self, srcfile):
        function = []
        a = []
        d=dict()
        ans,count = 0,0
        countl,counts = 0,0
        countspace = False
        startcal = False
        with codecs.open(srcfile, "rb", encoding='utf-8', errors='ignore') as code:
            pass

    def Readfile(self, srcfile):
        commentlist = [Comment.Single, Comment.Multiline, Token.Literal.String.Doc, Token.Text,Token.Comment.Preproc]
        inquotes = [Token.Literal.String.Double, Token.Literal.String.Single]
        totalcount=0
        srccount = 0
        comment=0
        with codecs.open(srcfile, "rb", encoding='utf-8', errors='ignore') as code:
            countchars = 0
            for ttype, value in self.lexer.get_tokens(code.read()):
                if ttype in inquotes:continue
                if ( '\n' in value or ttype==Token.Comment.Single) and countchars>0:
                    srccount += 1
                    countchars = 0
                if ('\n' in value):totalcount+=1
                if (ttype not in commentlist):
                    countchars += 1
                if ttype in [Comment.Single, Comment.Multiline, Token.Literal.String.Doc]:comment+=1
        return [srccount,totalcount,comment]
                

def RunMain():
    usage = "usage: %prog [options] <directory name>"
    parser = OptionParser(usage)

    parser.add_option("-l", "--lang", dest="lang", default='cpp',
                      help="programming language to determine the line of code (cpp, java or c#)")
    parser.add_option("-I", "--includes", dest="includespath", default='.',
                      help="list of include paths (seperated by ;)")

    (options, args) = parser.parse_args()
    if(len(args) < 1):
        print ("Invalid number of arguments. Use depends.py --help to see the details.")
    else:
        dirname = args[0]
        pathlist = options.includespath.split(';')
        pathlist.append('.')  # append current directory to search path
        print ("Language : %s" %(options.lang))
        print ("Dependency search path : %s" %options.includespath)
        print ("Counting loc ...")
        app = Countlines(options.lang, dirname)
        app.c.execute(""" CREATE TABLE IF NOT EXISTS Checkpoint(Checkpoint_name text PRIMARY KEY,DATE text)""")
        app.check="Checkpoint "+str(app.c.execute('SELECT COUNT(*) FROM Checkpoint').fetchone()[0]+1)
        app.c.execute('''INSERT INTO Checkpoint VALUES(?,?)''',(app.check,datetime.now()))
        app.conn.commit()
        # print (pd.read_sql_query("SELECT * FROM Checkpoint", app.conn))
        app.run(dirname)


if __name__ == "__main__":
    RunMain()
