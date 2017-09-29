import psycopg2
import logging
from datetime import datetime

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))


sql_product_type_table = """ CREATE TABLE IF NOT EXISTS prod_type(
            id serial primary key,
            p_name varchar(32),
            variant varchar(32),
            description varchar(32),
            saop integer );"""

sql_product_table = """ CREATE TABLE IF NOT EXISTS product( 
            id serial primary key,
            p_serial integer,
            production_datetime timestamp,
            product_type_id integer,
            hw_release varchar(32),
            notes varchar(32),
            foreign key (product_type_id) references prod_type(id));"""

sql_test_table = """ CREATE TABLE IF NOT EXISTS test(
            id serial primary key,
            product_id integer,
            test_type_id integer,
            val float,
            datetime timestamp,
            testna varchar(32),
            employee varchar(32),
            foreign key (product_id) references product(id),
            foreign key (test_type_id) references test_type(id) );"""

sql_test_type_table = """CREATE TABLE IF NOT EXISTS test_type(
            id serial primary key,
            test_name varchar(32),
            description varchar(200),
            units varchar(32) );"""

sql_prop_table = """CREATE TABLE IF NOT EXISTS property(
                    id serial primary key,
                    product_id integer,
                    prop varchar(32),
                    val varchar(32),
                    foreign key (product_id) references product(id)
                    );"""

sql_garo_insert_product = "INSERT INTO product (p_serial, production_datetime, product_type_id, hw_release, notes)VALUES (%s, %s, %s, %s, %s) RETURNING id;"
sql_garo_insert_type = "INSERT INTO prod_type (p_name, variant, description, saop) VALUES (%s, %s, %s, %s);"

sql_garo_insert_test = "INSERT INTO test(product_id, test_type_id, val, datetime, testna, employee) VALUES (%s, %s, %s, %s, %s, %s);"
sql_garo_insert_test_type = "INSERT INTO test_type(test_name, description, units) VALUES (%s, %s, %s) RETURNING id;"
sql_garo_insert_prop = "INSERT INTO property (product_id, prop, val) VALUES (%s, %s, %s);"


params = {
  'dbname': 'test_db',
  'user': 'admin',
  'password': 'admin',
  'host': '10.48.253.129',
  'port': 5432
}


class TestnaDB:
  def __init__(self, host):
    try:
      params['host'] = host
      self.conn = psycopg2.connect(**params)
      self.cur = self.conn.cursor()

      #self.delete_tables()

      self.cur.execute(sql_product_type_table)
      self.cur.execute(sql_product_table)
      self.conn.commit()
      self.cur.execute(sql_test_type_table)
      self.conn.commit()
      self.cur.execute(sql_test_table)
      self.cur.execute(sql_prop_table)
      self.conn.commit()

    except:
      module_logger.warning("Could not open DB with dbname %s, user %s, password %s, host %s, port %s",params['dbname'], params['user'], params['password'], params['host'], params['port'])
      raise ("Could not open base or create tables")

    module_logger.info("Opened the DB with dbname %s, user %s, password %s, host %s, port %s", params['dbname'], params['user'], params['password'], params['host'], params['port'])

  def delete_tables(self):
    '''
    Delete all existing tables
    :return: false if not successful
    '''
    try:
      self.cur.execute("DROP TABLE IF EXISTS property")
      self.cur.execute("DROP TABLE IF EXISTS test")
      self.cur.execute("DROP TABLE IF EXISTS test_type")
      self.cur.execute("DROP TABLE IF EXISTS product")
      self.cur.execute("DROP TABLE IF EXISTS prod_type")
      self.conn.commit()
    except Exception as ee:
      print("Exception occured during deleting tables")

  def insert_product_type(self, **kwargs):
    '''

    :param kwargs: (p_name = "product name" :str, description = "product desc": str, saop = saop code : int)
    :return:
    '''
    ## add aditional and execute only once
    p_name = kwargs.get('p_name', 'product_type')
    variant = kwargs.get('variant', 'product_variant')
    desc = kwargs.get('description', 'product_type_desc')
    saop = kwargs.get('saop', 000000)

    self.cur.execute("SELECT * FROM prod_type WHERE p_name='{}' AND variant='{}'".format(p_name, variant))
    self.conn.commit()
    prod_type = self.cur.fetchone()
    if prod_type is not None:
      return True, "Already exists"
    else:
      self.cur.execute(sql_garo_insert_type,(p_name, variant, desc, saop))
      self.conn.commit()

  def insert_test_type(self, **kwargs):
    '''
    :param kwargs: (test_name = "test name":str, description = "test type desc": str, units = units for value in test: int)
    :return:
    '''

    test_name = kwargs.get('test_name', 'test_type_name')
    desc = kwargs.get('description', 'test_type_desc')
    units = kwargs.get('units', 'None')

    self.cur.execute("SELECT * FROM test_type WHERE test_name='{}'".format(test_name))
    self.conn.commit()
    test_type = self.cur.fetchone()
    if test_type is not None:
      return True, (" Test type {} already exists".format(test_name))
    else:
      self.cur.execute(sql_garo_insert_test_type, (test_name, desc, units))
      self.conn.commit()

  def insert(self, dict_d, **kwargs):
    '''
    :param dict_d: dictionary of type ("name": db_test_type_name , "data": db_val(float)  , "status": str ->ok/fail , "level": 0-4 )
    :param kwargs: (testna = "testna name": str, variant = "name of product type": str, serial = "serial":int, hw_release = "hw_release of product":str)
    :return:
    '''

    testna_name = kwargs.get('testna', 'Unknown')
    employee = kwargs.get('employee','Strips')
    p_name = kwargs.get('p_name', 'product_type')
    variant = kwargs.get('variant', '00000')
    serial = kwargs.get('serial', '00000')
    hw_release = kwargs.get('hw_release', '0.00')
    time = datetime.now().isoformat(sep=' ')

    try:
      # get type id
      self.cur.execute("SELECT * FROM prod_type WHERE p_name='{}' AND variant='{}'".format(p_name, variant))
      last_type = self.cur.fetchone()
      #self.conn.commit()
      if last_type is not None:
        last_type_id = last_type[0]
        pass
      else:
        raise ("Product type does not exists")

      # search for existing product with serial
      self.cur.execute("SELECT * FROM product WHERE p_serial={}".format(serial))
      #self.conn.commit()
      product_fetch = self.cur.fetchone()

      if product_fetch is not None:
        id_of_new_product = product_fetch[0]
        pass
      else:
        self.cur.execute(sql_garo_insert_product,(serial, time , last_type_id, hw_release, "notes"))
        id_of_new_product = self.cur.fetchone()[0]
        self.conn.commit()


      for keys, values in dict_d.items():
        self.cur.execute("SELECT * FROM test_type WHERE test_name ='{}'".format(keys))
        id_of_test_type = self.cur.fetchone()[0]

        self.cur.execute(sql_garo_insert_test, (id_of_new_product, id_of_test_type, values[0], time, testna_name, employee))
        self.conn.commit()
    except:
      raise ("Failed to write to DB")

    module_logger.debug("Written product to DB with dbname %s, user %s, password %s, host %s, port %s", params['dbname'], params['user'], params['password'], params['host'], params['port'])
    return True, "Write to db succesfully"

  def close(self):
    self.conn.close()

############################################################
if __name__ == "__main__":
  dict_db = {}


  class dict_d:
    def __init__(self):
      pass


  # ("name": db_test_type_name , "data": db_val(float)  , "status": str ->ok/fail , "level": 0-4, "unit": str )

  dict_db["Vc"] = ("Vc", 15, "ok", 4, "V")
  dict_db["12V"] = ("12V", 12, "ok", 4, "V")
  dict_db["5V"] = ("5V", 5, "ok", 4, "V")
  dict_db["3V3"] = ("3V3", 3.3, "ok", 4, "V")
  dict_db["MCU flash"] = ("MCU flash", 0, "fail", 4, "bool")
  dict_db["relays"] = ("relays", 1, "ok", 0, "bool")
  dict_db["display"] = ("display", 1, "ok", 0, "bool")
  dict_db["keyboard"] = ("keyboard", 1, "ok", 0, "bool")
  dict_db["temperature"] = ("temperature", 2032, "ok", 0, "°C")
  dict_db["RTC"] = ("RTC", 0, "fail", 0, "bool")
  dict_db["flash test"] = ("flash test", 0, "fail", 0, "bool")
  dict_db["switches"] = ("switches", 0, "fail", 0, "bool")
  dict_db["board test"] = ("board test", 0, "fail", 0, "bool")
  dict_db["relay"] = ("relay", 0, "fail", 0, "bool")

  dict_db_one = {}
  dict_db_one["3V3"] = ("3V3", 3.34, "fail", 4)

  dict_db1 = dict_d
  dict_db1.serial = 235423
  dict_db1.variant = 'MVC basic'
  dict_db1.hw_release = '1.2'

  #module_logger.info("Starting postgresql ...")
  print("Start")
  db = TestnaDB('192.168.11.15')
  #db.insert_product_type(p_name="MVC basic", description="for garo", saop=2353)
  for test in dict_db:
    db.insert_test_type(test_name = dict_db[test][0], description = dict_db[test][0], units = dict_db[test][4])

  #db.insert(dict_db, testna = "TESTNA2", variant = "MVC", serial = 232352)
  #db.insert(dict_db_one, testna = "TESTNA2", variant = "MVC basic", serial = 242352)

  print("end")
  # db.delete_tables()s()