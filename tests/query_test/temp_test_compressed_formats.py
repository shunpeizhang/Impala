#!/usr/bin/env python
# Copyright (c) 2012 Cloudera, Inc. All rights reserved.

from os.path import join
from subprocess import call
from tests.common.test_vector import *
from tests.common.impala_test_suite import ImpalaTestSuite

# (file extension, table suffix) pairs
'''compression_formats = [
  ('.bz2',     'bzip'),
  ('.deflate', 'def'),
  ('.gz',      'gzip'),
  ('.snappy',  'snap'),
 ]'''

compression_formats = [('.bz2',     'bzip')]

class TestCompressedFormats(ImpalaTestSuite):
  """
  Tests that we support compressed RC and sequence files (see IMPALA-14: Files
  with .gz extension reported as 'not supported') and that unsupported formats
  fail gracefully.
  """
  @classmethod
  def get_workload(self):
    return 'functional-query'

  @classmethod
  def add_test_dimensions(cls):
    super(TestCompressedFormats, cls).add_test_dimensions()
    cls.TestMatrix.clear()
    #cls.TestMatrix.add_dimension(\
    #    TestDimension('file_format', *['rc', 'seq', 'text']))
    cls.TestMatrix.add_dimension(\
        TestDimension('file_format', *['text']))
    cls.TestMatrix.add_dimension(\
        TestDimension('compression_format', *compression_formats))

  def test_compressed_formats(self, vector):
    file_format = vector.get_value('file_format')
    extension, suffix = vector.get_value('compression_format')
    if file_format in ['rc', 'seq']:
      # Test that compressed RC/sequence files are supported
      db_suffix = '_%s_%s' % (file_format, suffix)
      self.copy_and_query_compressed_file(
       'tinytable', db_suffix, suffix, '000000_0', extension)

    elif file_format is 'text':
      # Test that that compressed text files (or at least text files with a
      # compressed extension) fail.
      db_suffix = ""
      self.copy_and_query_compressed_file(
        'tinytable', db_suffix, suffix, 'data.csv', extension,
        'Compressed text files are not supported')

    else:
      assert False, "Unknown file_format: %s" % file_format

  # TODO: switch to using hive metastore API rather than hive shell.
  def copy_and_query_compressed_file(self, table_name, db_suffix, compression_codec,
                                     file_name, extension, expected_error=None):
    # We want to create a test table with a compressed file that has a file
    # extension. We'll do this by making a copy of an existing table with hive.
    base_dir = '/test-warehouse'
    src_table = 'functional%s.%s' % (db_suffix, table_name)
    src_table_file = "%s%s" % (table_name, db_suffix)
    src_table_dir = join(base_dir, src_table_file)
    src_file = join(src_table_dir, file_name)

    # Make sure destination table uses suffix, even if use_suffix=False, so
    # unique tables are created for each compression format
    dest_table = '%s_copy' % src_table
    dest_table_file = '%s_%s_copy' % (table_name, compression_codec)
    dest_table_dir = join(base_dir, dest_table_file)
    dest_file = join(dest_table_dir, file_name + extension)

    drop_cmd = 'DROP TABLE IF EXISTS %s;' % (dest_table)
    hive_cmd = drop_cmd + 'CREATE TABLE %s LIKE %s;' % (dest_table, src_table)

    # Create the table
    call(["hive", "-e", hive_cmd]);
    # Copy the compressed file
    call(["hadoop", "fs", "-cp", src_file, dest_file])
    # Try to read the compressed file with extension
    query = 'select count(*) from %s' % dest_table
    print 'QUERY: %s' % query
    try:
      # Need to refresh
      self.client.refresh()
      result = self.execute_scalar(query)
      # Fail iff we expected an error
      assert expected_error is None, 'Query is expected to fail'
    except Exception as e:
      error_msg = str(e)
      print error_msg
      if expected_error is None or expected_error not in error_msg:
        print "Unexpected error: '%s'", error_msg
        raise
    finally:
      call(["hive", "-e", drop_cmd]);

