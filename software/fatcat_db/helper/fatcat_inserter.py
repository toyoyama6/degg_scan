"""This module provides the FatCatInserter

A class that takes care of inserting documents into the fatcat_db.
You can pass python dictionaries that are json-serializable to the insert function.
The istance will then write the document to disk as a .json file in a fixed directory.
The instance will check whether the document can be inserted without problem.
If that is the case, the insert is made, and the document is moved to a directory containing all good inserts.
If it is not the case, the insert is not made, and the file is moved to a directory of failed inserts.

"""
from fatcat_db import forwarder, runchecks, mongoreader
import json
import datetime
import os
import shutil


class FatCatInserter():
    """A class managing inserts into the FatCat database

    """

    _relative_path_to_data_dir = "fatcat_docs"

    def __init__(self):
        """Start the FatCatInserter

        Tries to establish a connection via ssh forwarding to the database in Madison

        """
        # see if the directories are set up properly, if not, create them
        self._path_to_data_dir = os.path.join(os.path.split(os.path.abspath(__file__))[0], self._relative_path_to_data_dir)
        # try to allocate the directories if they do not exist
        if not os.path.exists(self._path_to_data_dir):
            os.makedirs(self._path_to_data_dir)

        self._path_to_current_inserts = os.path.join(self._path_to_data_dir, "current_inserts")
        if not os.path.exists(self._path_to_current_inserts):
            os.makedirs(self._path_to_current_inserts)

        self._path_to_failed_inserts = os.path.join(self._path_to_data_dir, "failed_inserts")
        if not os.path.exists(self._path_to_failed_inserts):
            os.makedirs(self._path_to_failed_inserts)

        self._path_to_good_inserts = os.path.join(self._path_to_data_dir, "good_inserts")
        if not os.path.exists(self._path_to_good_inserts):
            os.makedirs(self._path_to_good_inserts)

        try:
            self._tunnel = forwarder.Tunnel()
        except Exception as e:
            print(e)

        # keep a persistent instance of the connection to the mongoDB at Madison
        self._mongoreader = mongoreader.MongoReader()

    def __del__(self):
        """Deconstruct the FatCatInserter instance

        """
        if hasattr(self, '_tunnel'):
            del(self._tunnel)
        if hasattr(self, '_mongoreader'):
            del(self._mongoreader)

    def insert_document(self, document, document_name=None):
        """Insert a document.

        Add a single document to the insert list and flush it into the fatcat database.

        Parameters
        ----------
        document : dictionary
            Document to insert.
        document_name : str, optional
            Name for the document, does not need to be specified. (default None)

        Returns
        -------
        bson.objectid.ObjectId
            The ObjectId of the docuemnt in the fatcat database

        """
        # construct the full filename
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S-%f")
        if document_name is None:
            suffix = "_insert.json"
        else:
            suffix = "_{name}_insert.json".format(name=document_name)
        shortname = timestamp + suffix
        full_path = os.path.join(self._path_to_current_inserts, shortname)
        # dump to file
        with open(full_path, 'w') as outfile:
            json.dump(document, outfile)

        # now actually try the insert
        ins = runchecks.Insert(full_path, mongoObj=self._mongoreader, verbosity="warning")

        if ins.passed:
            # with a successful insert, we move the json file to the good inserts directory
            shutil.move(os.path.join(self._path_to_current_inserts, shortname), os.path.join(self._path_to_good_inserts, shortname))
        else:
            # move the document over to the failed documents
            shutil.move(os.path.join(self._path_to_current_inserts, shortname), os.path.join(self._path_to_failed_inserts, shortname))

        return ins.ObjectId
