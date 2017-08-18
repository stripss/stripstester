import psycopg2
#import strips_tester
#import logging

#module_logger = logging.getLogger(".".join(("strips_tester", "postgr")))


sql_product_type_table = """ CREATE TABLE IF NOT EXISTS prod_type(
            id serial primary key,
            p_name varchar(32),
            description varchar(32),
            saop integer );"""

sql_product_table = """ CREATE TABLE IF NOT EXISTS product( 
            id serial primary key,
            serial integer,
            testna varchar(32),
            production_datetime varchar,
            product_type_id integer,
            hw_release varchar(32),
            notes varchar(32),
            foreign key (product_type_id) references prod_type(id));"""

sql_test_table = """ CREATE TABLE IF NOT EXISTS test(
            id serial primary key,
            product_id integer,
            test_type_id integer,
            val float,
            datetime varchar(32),
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

sql_garo_insert_product = "INSERT INTO product (serial, testna, production_datetime, product_type_id, hw_release, notes)VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;"
sql_garo_insert_type = "INSERT INTO prod_type (p_name, description, saop) VALUES (%s, %s, %s);"

sql_garo_insert_test = "INSERT INTO test(product_id, test_type_id, val, datetime ) VALUES (%s, %s, %s, %s);"
sql_garo_insert_test_type = "INSERT INTO test_type(test_name, description, units) VALUES (%s, %s, %s) RETURNING id;"
sql_garo_insert_prop = "INSERT INTO property (product_id, prop, val) VALUES (%s, %s, %s);"

test_dict = {}
test_dict["voltage 12V"] = ("voltage 12V", "12 V test", "V")
test_dict["voltage 3V3"] = ("voltage 3V3", "3.3 V test", "V")
test_dict["display"] = ("display", "garo 7 segment display", "bool")
test_dict["flash"] = ("flash", "writing to STM flash", "bool")
test_dict["temperature"] = ("temperature", "Measurement of current temperature", "°C")
test_dict["relays"] = ("relay test", "test of relays on PCB", "bool")

# strips_tester.current_product.tests["serial"] = ("serial", strips_tester.current_product.serial, "ok", 0)
# strips_tester.current_product.tests["variant"] = ("variant", strips_tester.current_product.variant, "ok", 0)
# strips_tester.current_product.tests["hw_release"] = ("hw_release", strips_tester.current_product.hw_release, "ok", 0)

strips_tester.current_product.serial = 235423
strips_tester.current_product.variant = 'MVC basic'
strips_tester.current_product.hw_release = '1.2'

strips_tester.current_product.tests["Vc"] = ("Vc", 15, "ok", 4)
strips_tester.current_product.tests["12V"] = ("12V", 12, "ok", 4)
strips_tester.current_product.tests["5V"] = ("5V", 5, "ok", 4)
strips_tester.current_product.tests["3V3"] = ("3V3", 3.3, "ok", 4)
strips_tester.current_product.tests["MCU flash"] = ("MCU flash", 0, "fail", 4)
strips_tester.current_product.tests["relays"] = ("relays", 1, "ok", 0)
strips_tester.current_product.tests["display"] = ("display", 1, "ok", 0)
strips_tester.current_product.tests["keyboard"] = ("keyboard", 1, "ok", 0)
strips_tester.current_product.tests["temperature"] = ("temperature", 2032, "ok", 0)
strips_tester.current_product.tests["RTC"] = ("RTC", 0, "fail", 0)
strips_tester.current_product.tests["flash test"] = ("flash test", 0, "fail", 0)
strips_tester.current_product.tests["switches"] = ("switches", 0, "fail", 0)
strips_tester.current_product.tests["board test"] = ("board test", 0, "fail", 0)
strips_tester.current_product.tests["relay"] = ("relay", 0, "fail", 0)

# ("name": db_test_type_name , "data": db_val(float)  , "status": str ->ok/fail , "level": 0-4 )
#strips_tester.current_product.tests["serial"] = ("varchar(32)", "float", "varchar(32)", "integer")

params = {
  'dbname': 'test_db',
  'user': 'admin',
  'password': 'admin',
  'host': '10.48.253.109',
  'port': 5432
}


class TestnaDB:
  def __init__(self):

    try:
      self.conn = psycopg2.connect(**params)
      self.cur = self.conn.curcsor()

      self.cur.execute(sql_product_type_table)
      self.cur.execute(sql_product_table)
      self.conn.commit()
      self.cur.execute(sql_test_type_table)
      self.conn.commit()
      self.cur.execute(sql_test_table)
      self.cur.execute(sql_prop_table)
      self.conn.commit()

    except:
      #module_logger("Could not open DB with dbname %s, user %s, password %s, host %s, port %s",params['dbname'], params['user'], params['password'], params['host'], params['port'])
      raise ("Could not open base or create tables")

    #module_logger("Opened the DB with dbname %s, user %s, password %s, host %s, port %s", params['dbname'], params['user'], params['password'], params['host'], params['port'])

  def delete_tables(self):
    self.cur.execute("DROP TABLE IF EXISTS prod_type")
    self.cur.execute("DROP TABLE IF EXISTS property")
    self.cur.execute("DROP TABLE IF EXISTS test")
    self.cur.execute("DROP TABLE IF EXISTS test_type")
    self.cur.execute("DROP TABLE IF EXISTS product")
    self.conn.commit()

  def insert_product_type(self, p_name, desc, saop):
    for test in strips_tester.current_product.tests:
      self.cur.execute(sql_garo_insert_type, (strips_tester.current_product.tests[test], strips_tester.current_product.tests[test], 0))

  def insert_all(self):
    try:
      self.cur.execute("SELECT * FROM prod_type WHERE p_name= %s", (strips_tester.current_product.variant,))
      last_type_id = self.cur.fetchone()[0]
      self.conn.commit()

      self.cur.execute(sql_garo_insert_product,(strips_tester.current_product.serial,"TESTNA2", "10-2-2017", last_type_id, strips_tester.current_product.hw_release, "notes"))
      id_of_new_product = self.cur.fetchone()[0]
      self.conn.commit()

      # ("name": db_test_type_name , "data": db_val(float)  , "status": str ->ok/fail , "level": 0-4 )
      for test in strips_tester.current_product.tests:
        self.cur.execute("SELECT * FROM test_type WHERE test_name = %s", (strips_tester.current_product.tests[test][0],))
        id_of_test_type = self.cur.fetchone()[0]

        self.cur.execute(sql_garo_insert_test, (id_of_new_product, id_of_test_type, strips_tester.current_product.tests[test][1], "10-2-2017"))
        #self.cur.execute(sql_garo_insert_prop, (id_of_new_product, "wifi", "ok"))
        self.conn.commit()
    except:
      raise ("Failed to write to DB")


if __name__ == "__main__":
    #parameter = str(sys.argv[1])
    module_logger.info("Starting postgresql ...")

    db = TestnaDB()
    db.delete_tables()