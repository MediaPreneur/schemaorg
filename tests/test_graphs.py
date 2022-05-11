import unittest
import os
import logging # https://docs.python.org/2/library/logging.html#logging-levels
import glob
import sys
sys.path.append( os.getcwd() ) 

from api import *
from parsers import *

#Setup testharness state BEFORE importing sdoapp
setInTestHarness(True)
from sdoapp import *

schema_path = './data/schema.rdfa'
examples_path = './data/examples.txt'
warnings = []

andstr = "\n AND\n  "
TYPECOUNT_UPPERBOUND = 1000
TYPECOUNT_LOWERBOUND = 500

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
setInTestHarness(True)

# Tests to probe the health of both schemas and code using graph libraries in rdflib
# Note that known failings can be annotated with @unittest.expectedFailure or @skip("reason...")


class SDOGraphSetupTestCase(unittest.TestCase):

  @classmethod
  def parseRDFaFilesWithRDFLib(cls):
    """Parse data/*rdfa into a data object and an error object with rdflib.
      We glob so that work-in-progress schemas can be stored separately. For
      final publication, a single schema file is used. Note that this does 
      not yet load or test any extension schemas beneath data/ext/*."""

    from rdflib import Graph
    files = glob.glob("data/*.rdfa")
    log.info(f"Found {len(files)} files via data/*rdfa.")
    cls.rdflib_errors = Graph()
    cls.rdflib_data = Graph()
    for f in files:
      log.info(f"Files to parse: {f}")
      log.info(f"Parsing URL {f} with rdflib RDFa parser. ")
      cls.rdflib_data.parse(f, format='rdfa', pgraph=cls.rdflib_errors)
        # log.info(self.rdflib_errors.serialize(format="nt"))

  @classmethod
  def setUpClass(cls):
    log.info("Graph tests require rdflib.")
    import unittest
    try:
      log.info("Trying to import rdflib...")
      import rdflib
      from rdflib import Graph
    except Exception as e:
      raise unittest.SkipTest(f"Need rdflib installed to do graph tests: {e}")

    read_schemas() # built-in parsers.
    cls.schemasInitialized = schemasInitialized
    log.info("SDOGraphSetupTestCase reading schemas using built-in parsers.")

    log.info("Attempting to parse data/*rdfa with rdflib.")
    SDOGraphSetupTestCase.parseRDFaFilesWithRDFLib()

  def test_schemasInitializedForGraph(self):
    self.assertEqual(self.schemasInitialized,True, "Schemas should be initialized during setup, so we can load them into a graph for testing.")

  def test_rdflib_happy(self):
    self.assertEqual(
        len(self.rdflib_errors) == 0,
        True,
        f'rdflib should have zero errors. {self.rdflib_errors.serialize(format="nt")}',
    )

  # SPARQLResult http://rdflib.readthedocs.org/en/latest/apidocs/rdflib.plugins.sparql.html
  # "A list of dicts (solution mappings) is returned"

  def test_found_sixplus_inverseOf(self):
    inverseOf_results = self.rdflib_data.query("select ?x ?y where { ?x <http://schema.org/inverseOf> ?y }")
    log.info(f"inverseOf result count: {len(inverseOf_results)}")
    self.assertEqual(
        len(inverseOf_results) >= 6,
        True,
        f"Six or more inverseOf expected. Found: {len(inverseOf_results)} ",
    )

  def test_even_number_inverseOf(self):
    inverseOf_results = self.rdflib_data.query("select ?x ?y where { ?x <http://schema.org/inverseOf> ?y }")
    self.assertEqual(
        len(inverseOf_results) % 2 == 0,
        True,
        f"Even number of inverseOf triples expected. Found: {len(inverseOf_results)} ",
    )

  @unittest.expectedFailure # autos
  def test_needlessDomainIncludes(self):
    global warnings
    # check immediate subtypes don't declare same domainIncludes
    # TODO: could we use property paths here to be more thorough?
    # rdfs:subClassOf+ should work but seems not to.
    ndi1= ("SELECT ?prop ?c1 ?c2 "
           "WHERE { "
           "?prop <http://schema.org/domainIncludes> ?c1 ."
           "?prop <http://schema.org/domainIncludes> ?c2 ."
           "?c1 rdfs:subClassOf ?c2 ."
           "FILTER (?c1 != ?c2) ."
           "}"
           "ORDER BY ?prop ")
    ndi1_results = self.rdflib_data.query(ndi1)
    if (len(ndi1_results)>0):
      for row in ndi1_results:
        warn = f'WARNING property {row["prop"]} defining domain, {row["c1"]}, [which is subclassOf] {row["c2"]} unnecessarily'
        warnings.append(warn)
        log.info(warn + "\n")
    self.assertEqual(
        len(ndi1_results),
        0,
        f"No subtype need redeclare a domainIncludes of its parents. Found: {len(ndi1_results)} ",
    )

  @unittest.expectedFailure
  def test_needlessRangeIncludes(self):
    global warnings
    # as above, but for range. We excuse URL as it is special, not best seen as a Text subtype.
    # check immediate subtypes don't declare same domainIncludes
    # TODO: could we use property paths here to be more thorough?
    nri1= ("SELECT ?prop ?c1 ?c2 "
             "WHERE { "
             "?prop <http://schema.org/rangeIncludes> ?c1 ."
             "?prop <http://schema.org/rangeIncludes> ?c2 ."
             "?c1 rdfs:subClassOf ?c2 ."
             "FILTER (?c1 != ?c2) ."
             "FILTER (?c1 != <http://schema.org/URL>) ." 
             "}"
             "ORDER BY ?prop ")
    nri1_results = self.rdflib_data.query(nri1)
    if (len(nri1_results)>0):
      for row in nri1_results:
        warn = f'WARNING property {row["prop"]} defining range, {row["c1"]}, [which is subclassOf] {row["c2"]} unnecessarily'
        warnings.append(warn)
        log.info(warn + "\n")
    self.assertEqual(
        len(nri1_results),
        0,
        f"No subtype need redeclare a rangeIncludes of its parents. Found: {len(nri1_results)}",
    )
    
#  def test_supersededByAreLabelled(self):
#    supersededByAreLabelled_results = self.rdflib_data.query("select ?x ?y ?z where { ?x <http://schema.org/supersededBy> ?y . ?y <http://schema.org/name> ?z }")
#    self.assertEqual(len(inverseOf_results ) % 2 == 0, True, "Even number of inverseOf triples expected. Found: %s " % len(inverseOf_results ) )


  def test_validRangeIncludes(self):
    nri1= ('''SELECT ?prop ?c1 
                 WHERE { 
                     ?prop <http://schema.org/rangeIncludes> ?c1 .
                     OPTIONAL{
                        ?c1 rdf:type ?c2 .
                        ?c1 rdf:type rdfs:Class .
                     }.
                     FILTER (!BOUND(?c2))
                 }
                 ORDER BY ?prop ''')
    nri1_results = self.rdflib_data.query(nri1)
    for row in nri1_results:
        log.info("Property %s invalid rangeIncludes value: %s\n" % (row["prop"],row["c1"]))
    self.assertEqual(
        len(nri1_results),
        0,
        f"RangeIncludes should define valid type. Found: {len(nri1_results)}",
    )

  def test_validDomainIncludes(self):
    nri1= ('''SELECT ?prop ?c1 
                 WHERE { 
                     ?prop <http://schema.org/domainIncludes> ?c1 .
                     OPTIONAL{
                        ?c1 rdf:type ?c2 .
                        ?c1 rdf:type rdfs:Class .
                     }.
                     FILTER (!BOUND(?c2))
                 }
                 ORDER BY ?prop ''')
    nri1_results = self.rdflib_data.query(nri1)
    for row in nri1_results:
        log.info("Property %s invalid domainIncludes value: %s\n" % (row["prop"],row["c1"]))
    self.assertEqual(
        len(nri1_results),
        0,
        f"DomainIncludes should define valid type. Found: {len(nri1_results)}",
    )

  # These are place-holders for more sophisticated SPARQL-expressed checks.

  @unittest.expectedFailure
  def test_readSchemaFromRDFa(self):
    self.assertTrue(True, False, "We should know how to locally get /docs/schema_org_rdfa.html but this requires fixes to api.py.")
    
      
    # 
    # TODO: https://github.com/schemaorg/schemaorg/issues/662
    #
    # self.assertEqual(len(ndi1_results), 0, "No domainIncludes or rangeIncludes value should lack a type. Found: %s " % len(ndi1_results ) )

def tearDownModule():
  global warnings
  if len(warnings) > 0:
      log.info("\nWarnings (%s):\n" % len(warnings))
  for warn in warnings:
    log.info(f"{warn}")

# TODO: Unwritten tests (from basics; easier here?)
#
# * different terms should not have identical comments
# * rdflib and internal parsers should have same number of triples
# * if x and y are inverseOf each other, the rangeIncludes types on x should be domainIncludes on y, and vice-versa.
# * need a few supporting functions e.g. all terms, all types, all properties, all enum values; candidates for api later but just use here first.

if __name__ == "__main__":
  unittest.main()
