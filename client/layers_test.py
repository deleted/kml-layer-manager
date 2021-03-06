import unittest
import mox
from layers import *

####
# Test Data
####

TEST_LAYER_PROPERTIES = dict((str(k), v) for k, v in {u'division_lod_min': None, u'compressed': True, u'busy': None, u'description': None, u'dynamic_balloons': False, u'auto_managed': False, u'division_lod_min_fade': None, u'division_lod_max_fade': None, u'division_lod_max': None, u'item_type': None, u'custom_kml': None, u'world': u'mars', u'uncacheable': False, u'icon': None, u'baked': None, u'division_size': None, u'contents': [], u'name': u'test_layer'}.items() )
TEST_LAYER_NAME = TEST_LAYER_PROPERTIES['name']
TEST_LAYER_ID = 1
LOREM_IPSUM = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec laoreet aliquet eleifend."

####

mock_LayersManagerClient = None # As the layers module retains a persistant client, so must the tests

class LayerTest(unittest.TestCase):
    def setUp(self):
        global mock_LayersManagerClient
        self.mox = mox.Mox()

        # Replace the mock_LayersManagerClient constructor with a stub-yielding method
        if not mock_LayersManagerClient:
            mock_LayersManagerClient = self.mox.CreateMock(lmc.LayersManagerClient)
        else:
            self.mox._mock_objects.append(mock_LayersManagerClient) # so ReplayAll / ResetAll will still work
        self.mock_LayersManagerClient = mock_LayersManagerClient
        def getLmc(*args): return self.mock_LayersManagerClient
        self.mox.stubs.Set(lmc, 'LayersManagerClient', getLmc)

    def tearDown(self):
        self.mox.VerifyAll()
        self.mox.ResetAll()
        self.mox.UnsetStubs()
        lmc._cms_client = None

    def test_get_default_client(self):
        self.mox.ReplayAll()

        client = get_default_client()
        self.assert_(isinstance(client, mox.MockObject))
        self.assert_(hasattr(client, 'Create'))
        self.assertEqual(get_default_client(), client) # make sure repeat calls yield the same object

    def test_create_layer(self):
        # TODO: test adding icons in create / update cases
        self.mock_LayersManagerClient.Create('layer', 0, name=TEST_LAYER_NAME, world='mars').AndReturn(TEST_LAYER_ID)
        self.mox.ReplayAll()

        layer = Layer(name='test_layer')
        self.assertRaises(MissingPropertyError, layer.save) # world is a required argument

        layer = Layer(name='test_layer', world='mars')
        layer.save()
        self.assertEquals(layer.id, TEST_LAYER_ID)
        self.assertEquals( layer.layer_id, TEST_LAYER_ID)
    
    def test_create_layer_with_icon(self):
        # TODO: test adding icons in create / update cases
        icon_url = 'http://somedomain.net/path/to/icon.png'
        icon_id = 3
        self.mock_LayersManagerClient.Create('layer', 0, name=TEST_LAYER_NAME, world='mars', icon=icon_url).AndReturn(TEST_LAYER_ID)
        self.mox.ReplayAll()

        layer = Layer(name='test_layer', world='mars', icon=icon_url)
        layer.save()
        self.assertEquals(layer.id, TEST_LAYER_ID)
        self.assertEquals( layer.layer_id, TEST_LAYER_ID)

    def _test_lmc_tests(self): # this test is disabled
        """ 
            This is just to make sure the mock LayersManagerClient constructor 
            always yields the same object.
        """
        a = lmc.LayersManagerClient('fee','fi','fo')
        self.assertEqual(a, self.mock_LayersManagerClient)
        a = lmc.LayersManagerClient('fee','fi','fo')
        self.assertEqual(a, self.mock_LayersManagerClient)

    def test_properties(self):
        self.mock_LayersManagerClient.Create('layer', 0, name=TEST_LAYER_NAME, world='mars').AndReturn(TEST_LAYER_ID)
        self.mock_LayersManagerClient.Query('layer', TEST_LAYER_ID, TEST_LAYER_ID).AndReturn(TEST_LAYER_PROPERTIES)
        newprops = TEST_LAYER_PROPERTIES.copy()
        newprops.update({'description': LOREM_IPSUM})
        self.mock_LayersManagerClient.Update('layer', 1, **newprops)
        self.mox.ReplayAll()

        layer = Layer(name='test_layer', world='mars')
        self.assertEqual(layer.dynamic_balloons, None) # Trying to access an unset property before the layer is saved.
        layer.save()
        mox.Replay(self.mock_LayersManagerClient)

        # RETRIEVE PROPERTIES
        self.assertEqual(layer.dynamic_balloons, False) # Should have the side effect of loading the properties from the cms
        self.assertEqual(layer._properties, TEST_LAYER_PROPERTIES)

        # UPDATE PROPERTIES
        layer.description = LOREM_IPSUM
        self.assertEqual(layer.description, LOREM_IPSUM)
        layer.save()
        self.assertEqual(layer.description, LOREM_IPSUM)
        

if __name__ == '__main__':
    unittest.main()
