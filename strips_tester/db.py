import psycopg2
import logging
from datetime import datetime

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))


sql_product_type_table = """ CREATE TABLE IF NOT EXISTS product_type(
            id serial primary key,
            type int UNIQUE,
            name varchar(32) UNIQUE,
            variant varchar(32),
            description varchar(32) );"""

sql_product_table = """ CREATE TABLE IF NOT EXISTS product( 
            id serial primary key,
            serial bigint UNIQUE,
            production_datetime timestamp,
            hw_release varchar(32),
            notes varchar(32),
            product_type_id integer,
            foreign key (product_type_id) references product_type(id));"""

sql_test_table = """ CREATE TABLE IF NOT EXISTS test(
            id serial primary key,
            value float,
            result varchar(8),
            datetime timestamp,
            test_device_name varchar(32),
            employee varchar(32),
            product_id integer,
            test_type_id integer,
            foreign key (product_id) references product(id),
            foreign key (test_type_id) references test_type(id) );"""

sql_test_type_table = """CREATE TABLE IF NOT EXISTS test_type(
            id serial primary key,
            name varchar(32) UNIQUE,
            description varchar(128),
            units varchar(32) );"""

sql_property_table = """CREATE TABLE IF NOT EXISTS property(
                    id serial primary key,
                    name varchar(32),
                    value varchar(32),
                    product_id integer,
                    foreign key (product_id) references product(id)
                    );"""

sql_insert_product = "INSERT INTO product (serial, production_datetime, hw_release, notes, product_type_id)VALUES (%s, %s, %s, %s, %s) RETURNING id;"
sql_insert_product_type = "INSERT INTO product_type (type, name, variant, description) VALUES (%s, %s, %s, %s);"

sql_insert_test = "INSERT INTO test(value, result, datetime, test_device_name, employee, product_id, test_type_id) VALUES (%s, %s, %s, %s, %s, %s, %s);"
sql_insert_test_type = "INSERT INTO test_type(name, description, units) VALUES (%s, %s, %s) RETURNING id;"

sql_insert_property= "INSERT INTO property (name, value, product_id) VALUES (%s, %s, %s);"


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
      self.cur.execute(sql_property_table)
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
      self.cur.execute("DROP TABLE IF EXISTS product_type")
      self.conn.commit()
      print("Tables were deleted")
    except Exception as ee:
      print("Exception occured during deleting tables")

  def insert_product_type(self, **kwargs):
    '''
    :param kwargs: (name = "product type name" :str, description = "product desc": str,)
    :return:
    '''
    ## add aditional and execute only once
    type = kwargs.get('type', 0000)
    name = kwargs.get('name', 'product_type')
    variant = kwargs.get('variant', 'product_variant')
    desc = kwargs.get('description', 'product_type_desc')

    self.cur.execute("SELECT * FROM product_type WHERE name='{}' AND variant='{}'".format(name, variant))
    self.conn.commit()
    prod_type = self.cur.fetchone()
    if prod_type is not None:
      return True, "Already exists"
    else:
      self.cur.execute(sql_insert_product_type,(type, name, variant, desc))
      self.conn.commit()

  def insert_test_type(self, **kwargs):
    '''
    :param kwargs: (name = "test name":str, description = "test type desc": str, units = units for value in test: int)
    :return:
    '''
    name = kwargs.get('name', 'test_type_name')
    desc = kwargs.get('description', 'test_type_desc')
    units = kwargs.get('units', 'None')

    self.cur.execute("SELECT * FROM test_type WHERE name='{}'".format(name))
    self.conn.commit()
    test_type = self.cur.fetchone()
    if test_type is not None:
      return True, (" Test type {} already exists".format(name))
    else:
      self.cur.execute(sql_insert_test_type, (name, desc, units))
      self.conn.commit()

  def insert(self, dict_d, **kwargs):
    '''
    :param dict_d: dictionary of type {"name": db_test_type_name : ["data": db_val(float), result: str="ok/fail", "level": 0-4, units[]]}
    :param kwargs: (serial: int = "product serial",
                    name: str="product_name",
                    variant = str: "name of product type",
                    hw_release: str="hardware release,
                    notes: str="add. notes",
                    production_datetime: int=170708,
                    test_device: str="testna name",
                    employee: str="employee")
    :return:
    '''
    serial = kwargs.get('serial', 0x0000000000000000)
    name = kwargs.get('name', 'product_name')  # product name
    variant = kwargs.get('variant', 'none')
    hw_release = kwargs.get('hw_release', '0.00')
    notes = kwargs.get('notes', 'notes')
    production_datetime = kwargs.get('production_datetime', 'NA')

    test_device_name = kwargs.get('test_device', 'Unknown')
    employee = kwargs.get('employee','Strips')

    test_datetime = datetime.utcnow()
    try:
      # get type id
      self.cur.execute("SELECT * FROM product_type WHERE name='{}' AND variant='{}'".format(name, variant))
      last_type = self.cur.fetchone()
      #self.conn.commit()
      if last_type is not None:
        product_type_id = last_type[0]
        pass
      else:
        raise ("Product type does not exists")

      # search for existing product with serial
      self.cur.execute("SELECT * FROM product WHERE serial={}".format(serial))
      #self.conn.commit()
      product_fetch = self.cur.fetchone()

      if product_fetch is not None:
        product_id = product_fetch[0]
        pass
      else:
        self.cur.execute(sql_insert_product,(serial, production_datetime , hw_release, notes, product_type_id))
        product_id = self.cur.fetchone()[0]
        self.conn.commit()


      for keys, values in dict_d.items():
        self.cur.execute("SELECT * FROM test_type WHERE name ='{}'".format(keys))
        test_type_id = self.cur.fetchone()[0]
        self.cur.execute(sql_insert_test, (values[0], values[1], test_datetime, test_device_name, employee, product_id, test_type_id))
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

  dict_tests = {
    "Vc": [15, "ok", 4, "V"],
    "3V3": [3.3, "ok", 4, "V"],
    "temperature": [2032, "ok", 0, "°C"]
  }

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

  #module_logger.info("Starting postgresql ...")
  print("Start")
  db = TestnaDB('192.168.11.15')

  db.insert_product_type(name="MVC basic", variant="2M RAM", description="for garo", type=2353)
  for test in dict_db:
    db.insert_test_type(name = dict_db[test][0], description = dict_db[test][0], units = dict_db[test][4])

  production_datetime = datetime.now().isoformat(sep=' ')
  db.insert(dict_tests, serial = 232352, name="MVC basic", variant="2M RAM", hw_release="v1.4", notes="my_notes", production_datetime=production_datetime,  test_device = "TESTNA2", employee="Jure")

  print("end")
  # db.delete_tables()s()
