// Copyright 2010 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Event handlers for the folder organization page.
 */

/*******************************************************************************
*                                  Constants                                   *
*******************************************************************************/

layermanager.folder = {};

/**
 * The maximum length of a context menu label to display. Longer labels will be
 * displayed with a trailing ellipsis.
 * @type {number}
 * @const
 */
layermanager.folder.MAXIMUM_LABEL_LENGTH = 20;

/**
 * The width and height of each icon, in pixels.
 * @type {number}
 * @const
 */
layermanager.folder.ICON_SIZE = 16;

/**
 * Paths and positions to various default icons.
 * @type {Object.<string, string>}
 * @const
 */
layermanager.folder.DEFAULT_ICONS = {
  layer: '/static/img/layer.png',
  folder: '/static/img/folder.png',
  entity: '/static/img/entity.png',
  link: '/static/img/link.png',
  create: '/static/img/create.png',
  remove: '/static/img/delete.png'
};

/*******************************************************************************
*                               Form Management                                *
*******************************************************************************/

/**
  * Collects the values of the folder form fields into a single object.
  * @return {Object} A map of field names to their values.
  */
layermanager.folder.collectFields = function() {
  return {
    folder_id: jQuery('#folder_id').val(),
    name: jQuery('#name').val(),
    description: jQuery('#description').val(),
    icon: jQuery('#icon').val(),
    region: jQuery('#region').val(),
    item_type: jQuery('#item_type').val(),
    custom_kml: jQuery('#custom_kml').val()
  };
};

/**
  * Shows the folder form filled with values from the specified folder.
  * @param {(string|number)} folderId The ID of the folder whose values are to
  *     to be used to fill the form.
  */
layermanager.folder.showForm = function(folderId) {
  jQuery('#folder_id').val(folderId);
  jQuery.each(
      layermanager.resources.folderDetails[folderId], function(key, value) {
    jQuery('#' + key).val(value || '').change();
  });
  jQuery('#folder_form').show();
};

/**
 * Hides the folder form.
 */
layermanager.folder.hideForm = function() {
  jQuery('#folder_form').hide();
};

/**
 * Fills the regions drop-down with values from layermanager.resources.regions.
 */
layermanager.folder.fillRegionsList = function() {
  var regionSelect = jQuery('#region');
  regionSelect.html('<option value="">None</option>');
  jQuery.each(layermanager.resources.regions, function(id, region) {
    if (region.name) {
      var label = region.name;
    } else {
      var box = region.coordinates;
      var label = layermanager.format.formatLatitude(box[0]) + ', ' +
                  layermanager.format.formatLongitude(box[1]) + ' to ' +
                  layermanager.format.formatLatitude(box[2]) + ', ' +
                  layermanager.format.formatLongitude(box[3]);
    }
    regionSelect.append('<option value="' + id + '">' + label + '</option>');
  });
};

/*******************************************************************************
*                              Tree Construction                               *
*******************************************************************************/

/**
  * Organizes the links, entities and folders into a tree depending on their id,
  * parent and index properties.
  * @param {[Object]} folders An array of folder objects with id, index and
  *     parent properties, the latter referencing the ids of other folders (null
  *     for folders residing in the layer root).
  * @param {[Object]} leaves An array of objects with id, index and parent
  *     properties, the latter referencing the ids of folders (null for objects
  *     residing in the layer root).
  * @return {Object} A tree structure of objects, with each object's children
  *     property filled.
  */
layermanager.folder.buildObjectTree = function(folders, leaves) {
  var tree = [];
  var lookup = {};

  // Organize folders.
  jQuery.each(folders, function(_, folder) {
    lookup[folder.id] = folder;
  });
  jQuery.each(folders, function(_, folder) {
    if (folder.parent === null) {
      tree.push(folder);
    } else {
      lookup[folder.parent].children.push(folder);
    }
  });

  // Organize entities and links.
  jQuery.each(leaves, function(_, leaf) {
    if (leaf.parent === null) {
      tree.push(leaf);
    } else {
      lookup[leaf.parent].children.push(leaf);
    }
  });

  // Sort lists.
  function compare(a, b) {
    return a.index - b.index;
  }
  function sort(node) {
    if (node.children) {
      jQuery.each(node.children, function(_, child) { sort(child); });
      node.children.sort(compare);
    }
  }
  sort({children: tree});

  return tree;
};

/**
  * Creates an HTML tree made up of nested <ul> elements from an object tree.
  * @param {string} container The id of the element that will contain the tree.
  * @param {Object} tree A tree of objects, where each object's children are
  *     contained in the parent's children property, and where each object has
  *     id, name and icon properties.
  */
layermanager.folder.buildListTree = function(container, tree) {
  function insertNode(parent, node) {
    var type = node.type + (node.icon ? '_' + node.icon : '');
    var item = jQuery('<li>').attr({rel: type, id: node.type + '_' + node.id});
    var content = jQuery('<a href="#">').text(node.name).appendTo(item);
    parent.append(item);
    if (node.children && node.children.length) {
      var sublist = jQuery('<ul>').appendTo(item);
      jQuery.each(node.children, function(_, node) {
        insertNode(sublist, node);
      });
    }
  }

  var item = jQuery('<li>').attr({rel: 'root', id: 'folder_root'});
  var content = jQuery('<a href="#">').text(layermanager.resources.layer.name)
      .appendTo(item);
  var subcontainer = jQuery('<ul>').appendTo(item);
  jQuery(container).append(item);
  jQuery.each(tree, function(_, node) {
    insertNode(jQuery(subcontainer), node);
  });
};

/**
  * Generates a list of types that can be used for jsTree's node type plugin.
  * The default types include "root", "folder", "entity" and "link", while the
  * dynamically generated types are of the form entity_{iconId}, folder_{iconId}
  * and link_{iconId} for each icon in the supplied #icon dropdown.
  * @return {Object} An object mapping from type names to type properties.
  */
layermanager.folder.generateTypesList = function() {
  var layerIconUrl = layermanager.util.getResourceUrl(
      layermanager.resources.layer.icon, layermanager.folder.ICON_SIZE);
  var types = {
    root: {
      valid_children: 'all',
      icon: {image: layerIconUrl || layermanager.folder.DEFAULT_ICONS.layer}
    },
    folder: {valid_children: 'all', icon: {
      image: layermanager.folder.DEFAULT_ICONS.folder
    }},
    entity: {valid_children: 'none', icon: {
      image: layermanager.folder.DEFAULT_ICONS.entity
    }},
    link: {valid_children: 'none', icon: {
      image: layermanager.folder.DEFAULT_ICONS.link
    }}
  };

  jQuery('option', '#icon').each(function() {
    var id = jQuery(this).val();
    var icon = layermanager.util.getResourceUrl(id, layermanager.folder.ICON_SIZE);
    types['folder_' + id] = {valid_children: 'all', icon: {image: icon}};
    types['entity_' + id] = {valid_children: 'none', icon: {image: icon}};
    types['link_' + id] = {valid_children: 'none', icon: {image: icon}};
  });

  return types;
};

/**
  * Creates a context menu that allows folder creation and deletion.
  * @return {Object} A context menu structure for use with the jsTree context
  *     menu plugin.
  */
layermanager.folder.makeContextMenu = function() {
  var newFolderCounter = 0;

  return {
    create: {
      label: 'Create Folder',
      action: function(obj) {
        this.create(obj, 'inside', {
          data: 'New Folder',
          attr: {rel: 'folder', id: ('folder_new_' + newFolderCounter++)}
        }, jQuery.noop, true);
      },
      icon: layermanager.folder.DEFAULT_ICONS.create
    },
    remove: {
      label: 'Delete',
      action: function(obj) {
        var node = obj.closest('li');
        var that = this;
        jQuery('li', node).each(function() {
          that.move_node(this, '#folder_root', 'inside');
        });
        this.remove(obj);
      },
      icon: layermanager.folder.DEFAULT_ICONS.remove
    }
  };
};

/**
  * Converts a tree made of nested <ul> elements into an interactive jsTree and
  * configures the appropriate jsTree plugins.
  * @param {string} container The id of the element that will contain the tree.
  */
layermanager.folder.initJsTree = function(container) {
  var types = layermanager.folder.generateTypesList();
  var fullContextMenu = layermanager.folder.makeContextMenu();

  // Delete default jsTree context menu items.
  jQuery.jstree.defaults.contextmenu.items = {};

  // Configure jsTree plugins.
  jQuery(container).jstree({
    core: {initially_open: 'folder_root'},
    types: {valid_children: 'root', types: types},
    dnd: {copy_modifier: null},
    crrm: {move: {check_move: function(move) {
      var isSourceRoot = (move.o.attr('id') == 'folder_root');
      var isTargetRoot = (move.r.attr('id') == 'folder_root');
      return (move.p == 'inside' && !isSourceRoot) ||
             (!isSourceRoot && !isTargetRoot);
    }}},
    ui: {select_multiple_modifier: null},
    contextmenu: {items: function(sourceNode) {
      var sourceKind = sourceNode.attr('rel');
      if (sourceKind == 'root') {
        return {create: fullContextMenu.create};
      } else if (sourceKind.match(/^(folder)/)) {
        return fullContextMenu;
      } else {
        return {};
      }
    }},
    plugins: [
      'themes', 'html_data', 'dnd', 'crrm', 'types', 'contextmenu', 'ui'
    ]
  });
};

/**
  * Sets up handlers for jsTree events that pass any changes in the tree to the
  * enqueueBackendEvent() function.
  */
layermanager.folder.setupTreeEventHandlers = function() {
  var tree = jQuery.jstree._reference('#folder_root').get_container();

  tree.bind('delete_node.jstree', function(_, data) {
    layermanager.folder.sync.enqueueBackendEvent('delete', data.rslt.obj);
  }).bind('create_node.jstree', function(_, data) {
    var target = data.rslt.obj;
    var parent = data.rslt.parent.attr('id');
    layermanager.folder.sync.enqueueBackendEvent('create', target, parent);
    layermanager.folder.sync.enqueueBackendEvent('move', target, parent);
  }).bind('move_node.jstree', function(_, data) {
    var target = data.rslt.o;
    var parent = target.parent().closest('li');
    layermanager.folder.sync.enqueueBackendEvent(
        'move', target, parent.attr('id'));
  }).bind('click.jstree', function(event) {
    var node = jQuery(event.target).closest('li');
    if (node) {
      var id = node.attr('id').match(/^folder_(\d+)$/);
      if (id) {
        layermanager.folder.showForm(id[1]);
      } else {
        layermanager.folder.hideForm();
      }
    }
  });
};

/*******************************************************************************
*                           Backend Synchronization                            *
*******************************************************************************/

layermanager.folder.sync = {};

/**
 * A global queue of events that have not yet been applied on the backend.
 */
layermanager.folder.sync.pendingActions = [];

/**
  * A global flag indicating whether an event is currently being sent to the
  * backend.
  */
layermanager.folder.sync.eventInProgress = false;

/**
  * Triggers the next event from the pendingActions queue if there are any. Also
  * updates the synchronization indicator to reflect whether any events are
  * still pending. This should be called whenever an event is done or a new
  * event is added to an empty queue while no action is in progress.
  */
layermanager.folder.sync.processNextEvent = function() {
  layermanager.folder.sync.eventInProgress = false;
  var actionPending = layermanager.folder.sync.pendingActions.length > 0;
  jQuery('#folder_synchronized').toggle(!actionPending);
  jQuery('#folder_synchronizing').toggle(actionPending);
  if (actionPending) {
    layermanager.folder.sync.triggerBackendEvent.apply(
        window, layermanager.folder.sync.pendingActions.shift());
  }
  layermanager.folder.sync.eventInProgress = actionPending;
};

/**
  * Adds a new event to the event queue, and processes it if no other events are
  * being processed.
  * @param {string} action A string indicating the kind of action to perform.
  *     One of the values:
  *     create: Creates a new folder.
  *     delete: Deletes the folder.
  *     move: Updates the contents of the folder specified by opt_arg with its
  *       current contents. The folder specified by opt_arg should usually be
  *       the parent of the one specified by target.
  * @param {Element} target A jQuery-wrapped <li> DOM element indicating the
  *     node on which the perform the specified action.
  * @param {Object=} opt_arg An action-specific argument. The type and value of
  *     this depends on the type of the event (action):
  *     create: The ID of the parent folder.
  *     delete: Ignored.
  *     move: The ID of the folder whose content are to be updated.
  */
layermanager.folder.sync.enqueueBackendEvent = function(action, target,
                                                        opt_arg) {
  layermanager.folder.sync.pendingActions.push([action, target, opt_arg]);
  if (!layermanager.folder.sync.eventInProgress) {
    layermanager.folder.sync.processNextEvent();
  }
};

/**
  * Immediately processes an event, sending an appropriate POST request to
  * the backend. Receives the same parameters as enqueueBackendEvent().
  *
  * @param {string} action The type of event to trigger.
  *     See enqueueBackendEvent() for details.
  * @param {Object=} target A jQuery-wrapped <li> node inside jsTree
  *     indicating the folder to operate on.
  * @param {Object=} opt_arg An argument to pass to the backend event.
  *     See enqueueBackendEvent() for details.
  */
layermanager.folder.sync.triggerBackendEvent = function(action, target,
                                                        opt_arg) {
  var targetId = target.attr('id');
  var targetIdParts = targetId.match(/^(.+)_([^_]+)$/);
  var kind = targetIdParts[1];
  var id = targetIdParts[2];

  switch (action) {
    case 'create':
      layermanager.folder.sync.create(targetId, opt_arg.toString());
      break;
    case 'delete':
      layermanager.folder.sync.destroy(id);
      break;
    case 'move':
      var children = jQuery('#' + opt_arg).children('ul').children('li');
      layermanager.folder.sync.updateContents(opt_arg.toString(), children);
      break;
    default:
      layermanager.util.reportError(
        'Attempted to sync an invalid action type.');
  }
};

/**
  * Sends a backend event to creates a folder.
  * @param {string} nodeId The ID of the node that represents the new folder.
  *     Used to update the node with its real backend ID once the request
  *     succeeds.
  * @param {string} parent The ID of the node that contains the new folder.
  */
layermanager.folder.sync.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'folder',
  collect: function(nodeId, parent) {
    parent = parent.match(/^folder_(.+)$/)[1];
    parent = (parent == 'root') ? '' : parent;
    // The node_id parameter is ignored by the backend; used here just to pass
    // to the success handler.
    return {node_id: nodeId, folder: parent, name: 'New Folder'};
  },
  succeed: function(result, fields) {
    layermanager.resources.folderDetails[result] = {
      name: fields.name,
      icon: null,
      description: '',
      region: null,
      item_type: '',
      custom_kml: '',
      parent: fields.parent,
      index: 0
    };
    jQuery('#' + fields.node_id).attr('id', 'folder_' + result);
    layermanager.folder.sync.processNextEvent();
  }
});

/**
  * Sends a backend event to delete a folder.
  * @param {string} folderId The ID of the folder to delete.
  */
layermanager.folder.sync.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'folder',
  collect: function(folderId) {
    return {folder_id: folderId};
  },
  succeed: function() {
    layermanager.folder.sync.processNextEvent();
    layermanager.folder.hideForm();
  }
});

/**
  * Sends a backend event to update a folder's properties.
  * @param {string} folderId The ID of the folder to update.
  * @param {Object.<string>} properties A map of property names to values.
  */
layermanager.folder.sync.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'folder',
  collect: layermanager.folder.collectFields,
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(_, fields) {
    layermanager.resources.folderDetails[fields.folder_id] = fields;
    var tree = jQuery.jstree._reference('#folder_canvas');
    var node = jQuery('#folder_' + fields.folder_id);
    tree.rename_node(node, fields.name);
    tree.set_type(fields.icon ? 'folder_' + fields.icon : 'folder', node);
    // Adding and removing a random class forces a style refresh.
    node.addClass('-refresh-dummy').removeClass('-refresh-dummy');
  }
});

/**
  * Sends a backend event to update a folder's contents.
  * @param {string} parentNodeId The ID of either the root or the folder
  *     node to which to move the specified contents.
  * @param {[Element]} contentNodes A jQuery-wrapped array of nodes (either
  *     folders or entities) which will be moved to the specified parent.
  */
layermanager.folder.sync.updateContents = layermanager.util.makeHandler({
  action: 'move',
  type: 'folder',
  collect: function(parentNodeId, contentNodes) {
    var parentId = parentNodeId.match(/^folder_(.+)$/)[1];
    var contents = contentNodes.map(function() {
      var id = jQuery(this).attr('id');
      var item = id.match(/^(folder|entity|link)_(\d+)$/);
      return item[1] + ',' + item[2];
    }).get();
    return {
      parent: (parentId == 'root') ? '' : parentId,
      contents: contents
    };
  },
  validate: function(fields) {
    return fields !== false;
  },
  succeed: layermanager.folder.sync.processNextEvent
});

/*******************************************************************************
*                                     Main                                     *
*******************************************************************************/

/**
  * Initializes the jsTree, its plugins and events handlers to synchronize its
  * state to the backend.
  */
layermanager.folder.initialize = function() {
  if (layermanager.resources.layer.autoManaged) {
    jQuery('#auto_managed_message').show();
    return;
  }

  var tree = layermanager.folder.buildObjectTree(
      layermanager.resources.folders,
      layermanager.resources.leaves);
  var container = '#folder_canvas';
  layermanager.folder.buildListTree(container, tree);
  layermanager.folder.initJsTree(container);
  layermanager.folder.setupTreeEventHandlers();
  jQuery('#folder_synchronized').show();
  jQuery('#folder_canvas').show();

  layermanager.folder.fillRegionsList();
  layermanager.ui.visualizeIconSelect(jQuery('#icon'));
  jQuery('#folder_form_apply').click(layermanager.folder.sync.update);
};

google.setOnLoadCallback(layermanager.folder.initialize);
