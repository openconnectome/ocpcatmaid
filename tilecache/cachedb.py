
from django.conf import settings

import MySQLdb
import os

import logging
logger=logging.getLogger("ocpcatmaid")


class CacheDB:
  """MySQL interface for cache management"""

  def __init__(self):

    try:
      self.conn = MySQLdb.connect (host = 'localhost',
                            user = settings.USER,
                            passwd = settings.PASSWD,
                            db = settings.DBNAME )
    except MySQLdb.Error, e:
      logger.error("Failed to connect to database: %s, %s" % (settings.DBNAME, e))
      raise


# Some technique to make sure we don't fetch the same thing twice concurrently?


  def touch(self, tkey):
    """Update the reference time on a tile"""

    cursor = self.conn.cursor()

    sql = "UPDATE contents SET reftime=NOW() WHERE highkey={} AND lowkey={}".format(tkey[0],tkey[1])
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to touch tilekey %s.  Error %d: %s. sql=%s" % (tkey, e.args[0], e.args[1], sql))
      raise

    self.conn.commit()


  def insert(self, tkey, filename):
    """Add a tile to the cache contents.  Remove from prefetch queue."""

    cursor = self.conn.cursor()
    
    sql = "INSERT INTO contents (highkey,lowkey,filename,reftime) VALUES ({},{},'{}', NOW());".format(tkey[0],tkey[1],filename)

    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to add tile to contents %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise

    self.conn.commit()


  def size ( self ):
    """Return the size of the cache in nunmber of tiles"""

    cursor = self.conn.cursor()

    # determine the current cache size
    sql = "SELECT SUM(numtiles) FROM metadata;"
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to query cache size %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise
    
    return int(cursor.fetchone()[0])


  def increase ( self, numtiles ):
    """Add tiles to the cache"""

    cursor = self.conn.cursor()

    # determine the current cache size
    sql = "UPDATE metadata SET numtiles=numtiles+{}".format(numtiles)
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to query cache size %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise
   
    self.conn.commit()

  def decrease ( self, numtiles ):
    """Remove tiles from the cache"""

    cursor = self.conn.cursor()

    # determine the current cache size
    sql = "UPDATE metadata SET numtiles=numtiles-{}".format(numtiles)
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to query cache size %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise
   
    self.conn.commit()


  def reclaim ( self, numitems ):
    """Reduce the cache size to a target"""

    cursor = self.conn.cursor()

    sql = "SELECT highkey, lowkey, filename FROM contents ORDER BY reftime ASC LIMIT {}".format(numitems)

    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to query cache for reclamation s%d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise

    result = cursor.fetchall()
    tilekeys = [(int(item[0]),int(item[1])) for item in result]
    files = [item[2] for item in result]

    # Delete the files
    for fname in files:
      # remove the file but don't quit
      try:
        os.remove ( fname )
      except Exception, e:
        logger.error("Failed to remove file %s. Error %s" % ( fname, e ))

    sql = "DELETE FROM contents WHERE (highkey,lowkey) IN (%s)"
    in_p=', '.join(map(lambda x: str(x), tilekeys))
    sql = sql % in_p
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to remove items from cache %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise

    self.decrease ( numitems )
    self.conn.commit()

  def getDatasetKey ( self, token ):

    cursor = self.conn.cursor()

    sql = "SELECT (datasetid) FROM datasets WHERE dataset='{}';".format(token)
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to insert dataset %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise

    # 0 is no dataset.  It will never match in the cache. 
    # The dataset will get created on fetch.
    r = cursor.fetchone()
    if r == None:
      return 0  
    else:
      return r[0]

  def addDataset ( self, token ):
    """Add a dataset to the list of cacheable datasets"""

    
    cursor = self.conn.cursor()

# I would like to run this as a transaction, but can't get it to work
# because `I can't figure out how to read the autoincrement value
#    sql = "START TRANSACTION;"
    sql = ""
    sql += "INSERT INTO datasets (dataset) VALUES ('{}');".format(token)
    try:
      cursor.execute ( sql )
    except MySQLdb.Error, e:
      logger.warning ("Failed to insert dataset %d: %s. sql=%s" % (e.args[0], e.args[1], sql))
      raise

    self.conn.commit()