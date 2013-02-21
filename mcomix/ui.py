"""ui.py - UI definitions for main window.
"""

import os.path
import gtk

from mcomix import bookmark_menu
from mcomix import openwith_menu
from mcomix import edit_dialog
from mcomix import enhance_dialog
from mcomix import preferences_dialog
from mcomix import recent
from mcomix import dialog_handler
from mcomix import constants
from mcomix import status
from mcomix import file_chooser_main_dialog
from mcomix.preferences import prefs
from mcomix.library import main_dialog as library_main_dialog

class MainUI(gtk.UIManager):

    def __init__(self, window):
        gtk.UIManager.__init__(self)

        self._window = window
        self._tooltipstatus = status.TooltipStatusHelper(self, window.statusbar)

        # ----------------------------------------------------------------
        # Create actions for the menus.
        # ----------------------------------------------------------------
        self._actiongroup = gtk.ActionGroup('mcomix-main')
        self._actiongroup.add_actions([
            ('copy_page', gtk.STOCK_COPY, _('_Copy'), None,
                _('Copies the current page to clipboard.'),
                window.clipboard.copy_page),
            ('delete', gtk.STOCK_DELETE, _('_Delete'), 'Delete',
                _('Deletes the current file or archive from disk.'),
                window.delete),
            ('next_page', 'mcomix-next-page', _('_Next page'),
                'Page_Down', _('Next page'), window.next_page),
            ('previous_page', 'mcomix-previous-page', _('_Previous page'),
                'Page_Up', _('Previous page'), window.previous_page),
            ('first_page', 'mcomix-goto-first-page', _('_First page'),
                'Home', _('First page'), window.first_page),
            ('last_page', 'mcomix-goto-last-page', _('_Last page'),
                'End', _('Last page'), window.last_page),
            ('go_to', gtk.STOCK_JUMP_TO, _('_Go to page...'),
                'G', _('Go to page...'), window.page_select),
            ('refresh_archive', gtk.STOCK_REFRESH, _('Re_fresh'), '<control><shift>R',
                _('Reloads the currently opened files or archive.'),
                window.filehandler.refresh_file),
            ('next_archive', 'mcomix-next-archive', _('Next _archive'),
                '<control><shift>N', _('Next archive'), window.filehandler._open_next_archive),
            ('previous_archive', 'mcomix-previous-archive', _('Previous a_rchive'),
                '<control><shift>P', _('Previous archive'), window.filehandler._open_previous_archive),
            ('next_directory', 'mcomix-next-directory', _('Next directory'),
                '<control>N', _('Next directory'), window.filehandler.open_next_directory),
            ('previous_directory', 'mcomix-previous-directory', _('Previous directory'),
                '<control>P', _('Previous directory'), window.filehandler.open_previous_directory),
            ('zoom_in', gtk.STOCK_ZOOM_IN, _('Zoom _In'),
                'KP_Add', None, window.manual_zoom_in),
            ('zoom_out', gtk.STOCK_ZOOM_OUT, _('Zoom _Out'),
                'KP_Subtract', None, window.manual_zoom_out),
            ('zoom_original', gtk.STOCK_ZOOM_100, _('_Normal Size'),
                '<Control>0', None, window.manual_zoom_original),
            ('minimize', gtk.STOCK_LEAVE_FULLSCREEN, _('Mi_nimize'),
                'n', None, window.minimize),
            ('close', gtk.STOCK_CLOSE, _('_Close'), None,
                _('Closes all opened files.'), window.filehandler.close_file),
            ('quit', gtk.STOCK_QUIT, _('_Quit'),
                None, None, window.close_program),
            ('save_and_quit', gtk.STOCK_QUIT, _('_Save and quit'),
                '<Control><shift>q',
                _('Quits and restores the currently opened file next time the program starts.'),
                window.save_and_terminate_program),
            ('rotate_90', 'mcomix-rotate-90', _('_Rotate 90 degrees CW'),
                'r', None, window.rotate_90),
            ('rotate_180','mcomix-rotate-180', _('Rotate 180 de_grees'),
                None, None, window.rotate_180),
            ('rotate_270', 'mcomix-rotate-270', _('Rotat_e 90 degrees CCW'),
                '<Shift>r', None, window.rotate_270),
            ('flip_horiz', 'mcomix-flip-horizontal', _('Fli_p horizontally'),
                None, None, window.flip_horizontally),
            ('flip_vert', 'mcomix-flip-vertical', _('Flip _vertically'),
                None, None, window.flip_vertically),
            ('extract_page', gtk.STOCK_SAVE_AS, _('Save _As'),
                '<Control><Shift>s', None, window.extract_page),
            ('menu_zoom', 'mcomix-zoom', _('_Zoom')),
            ('menu_recent', gtk.STOCK_DND_MULTIPLE, _('_Recent')),
            ('menu_bookmarks_popup', 'comix-add-bookmark', _('_Bookmarks')),
            ('menu_bookmarks', None, _('_Bookmarks')),
            ('menu_toolbars', None, _('T_oolbars')),
            ('menu_edit', None, _('_Edit')),
            ('menu_open_with', gtk.STOCK_OPEN, _('Open _with')),
            ('menu_file', None, _('_File')),
            ('menu_view', None, _('_View')),
            ('menu_view_popup', 'comix-image', _('_View')),
            ('menu_go', None, _('_Go')),
            ('menu_go_popup', gtk.STOCK_GO_FORWARD, _('_Go')),
            ('menu_tools', None, _('_Tools')),
            ('menu_help', None, _('_Help')),
            ('menu_transform', 'mcomix-transform', _('_Transform image')),
            ('menu_autorotate', None, _('_Auto-rotate image')),
            ('menu_autorotate_width', None, _('...when width exceeds height')),
            ('menu_autorotate_height', None, _('...when height exceeds width')),
            ('expander', None, None, None, None, None)])

        self._actiongroup.add_toggle_actions([
            ('fullscreen', gtk.STOCK_FULLSCREEN, _('_Fullscreen'),
                'f', _('Fullscreen mode'), window.change_fullscreen),
            ('double_page', 'mcomix-double-page', _('_Double page mode'),
                'd', _('Double page mode'), window.change_double_page),
            ('toolbar', None, _('_Toolbar'),
                None, None, window.change_toolbar_visibility),
            ('menubar', None, _('_Menubar'),
                '<Control>M', None, window.change_menubar_visibility),
            ('statusbar', None, _('St_atusbar'),
                None, None, window.change_statusbar_visibility),
            ('scrollbar', None, _('S_crollbars'),
                None, None, window.change_scrollbar_visibility),
            ('thumbnails', None, _('Th_umbnails'),
                'F9', None, window.change_thumbnails_visibility),
            ('hide all', None, _('H_ide all'),
                'i', None, window.change_hide_all),
            ('manga_mode', 'mcomix-manga', _('_Manga mode'),
                'm', _('Manga mode'), window.change_manga_mode),
            ('invert_scroll', gtk.STOCK_UNDO, _('Invert smart scroll'),
                'x', _('Invert smart scrolling direction.'), window.change_invert_scroll),
            ('keep_transformation', None, _('_Keep transformation'), 'k',
                _('Keeps the currently selected transformation for the next pages.'),
                window.change_keep_transformation),
            ('slideshow', gtk.STOCK_MEDIA_PLAY, _('Start _slideshow'),
                '<Control>S', _('Start slideshow'), window.slideshow.toggle),
            ('lens', 'mcomix-lens', _('Magnifying _lens'),
                'l', _('Magnifying lens'), window.lens.toggle),
            ('stretch', None, _('Stretch small images'), 'y',
                _('Stretch images to fit to the screen, depending on zoom mode.'),
                window.change_stretch)])

        # Note: Don't change the default value for the radio buttons unless
        # also fixing the code for setting the correct one on start-up in main.py.
        self._actiongroup.add_radio_actions([
            ('best_fit_mode', 'mcomix-fitbest', _('_Best fit mode'),
                'b', _('Best fit mode'), constants.ZOOM_MODE_BEST),
            ('fit_width_mode', 'mcomix-fitwidth', _('Fit _width mode'),
                'w', _('Fit width mode'), constants.ZOOM_MODE_WIDTH),
            ('fit_height_mode', 'mcomix-fitheight', _('Fit _height mode'),
                'h', _('Fit height mode'), constants.ZOOM_MODE_HEIGHT),
            ('fit_size_mode', 'mcomix-fitsize', _('Fit _size mode'),
                's', _('Fit to size mode'), constants.ZOOM_MODE_SIZE),
            ('fit_manual_mode', 'mcomix-fitmanual', _('M_anual zoom mode'),
                'a', _('Manual zoom mode'), constants.ZOOM_MODE_MANUAL)],
            3, window.change_zoom_mode)

        # Automatically rotate image if width>height or height>width
        self._actiongroup.add_radio_actions([
            ('no_autorotation', None, _('Never'),
             None, None, constants.AUTOROTATE_NEVER),
            ('rotate_90_width', 'mcomix-rotate-90', _('_Rotate 90 degrees CW'),
             None, None, constants.AUTOROTATE_WIDTH_90),
            ('rotate_270_width', 'mcomix-rotate-270', _('Rotat_e 90 degrees CCW'),
             None, None, constants.AUTOROTATE_WIDTH_270),
            ('rotate_90_height', 'mcomix-rotate-90', _('_Rotate 90 degrees CW'),
             None, None, constants.AUTOROTATE_HEIGHT_90),
            ('rotate_270_height', 'mcomix-rotate-270', _('Rotat_e 90 degrees CCW'),
             None, None, constants.AUTOROTATE_HEIGHT_270)],
            prefs['auto rotate depending on size'], window.change_autorotation)

        self._actiongroup.add_actions([
            ('about', gtk.STOCK_ABOUT, _('_About'),
             None, None, dialog_handler.open_dialog)], (window, 'about-dialog'))

        self._actiongroup.add_actions([
            ('comments', 'mcomix-comments', _('Co_mments...'),
             'c', None, dialog_handler.open_dialog)], (window, 'comments-dialog'))

        self._actiongroup.add_actions([
            ('properties', gtk.STOCK_PROPERTIES, _('Proper_ties'),
                '<Alt>Return', None, dialog_handler.open_dialog)], (window,'properties-dialog'))

        self._actiongroup.add_actions([
            ('preferences', gtk.STOCK_PREFERENCES, _('Pr_eferences'),
                'F12', None, preferences_dialog.open_dialog)], (window))

        # Some actions added separately since they need extra arguments.
        self._actiongroup.add_actions([
            ('edit_archive', gtk.STOCK_EDIT, _('_Edit archive...'), None,
                _('Opens the archive editor.'),
                edit_dialog.open_dialog),
            ('open', gtk.STOCK_OPEN, _('_Open...'),
                None, None, file_chooser_main_dialog.open_main_filechooser_dialog),
            ('enhance_image', 'mcomix-enhance-image', _('En_hance image...'),
                'e', None, enhance_dialog.open_dialog)], window)

        self._actiongroup.add_actions([
            ('library', 'mcomix-library', _('_Library...'),
                '<Control>L', None, library_main_dialog.open_dialog)], window)

        ui_description = """
        <ui>
            <toolbar name="Tool">
                <toolitem action="previous_archive" />
                <toolitem action="first_page" />
                <toolitem action="previous_page" />
                <toolitem action="go_to" />
                <toolitem action="next_page" />
                <toolitem action="last_page" />
                <toolitem action="next_archive" />
                <separator />
                <toolitem action="slideshow" />
                <toolitem action="expander" />
                <toolitem action="best_fit_mode" />
                <toolitem action="fit_width_mode" />
                <toolitem action="fit_height_mode" />
                <toolitem action="fit_size_mode" />
                <toolitem action="fit_manual_mode" />
                <separator />
                <toolitem action="double_page" />
                <toolitem action="manga_mode" />
                <separator />
                <toolitem action="lens" />
            </toolbar>

            <menubar name="Menu">
                <menu action="menu_file">
                    <menuitem action="open" />
                    <menu action="menu_recent" />
                    <menuitem action="library" />
                    <separator />
                    <menuitem action="extract_page" />
                    <menuitem action="refresh_archive" />
                    <menuitem action="properties" />
                    <menu action="menu_open_with"></menu>
                    <separator />
                    <menuitem action="delete" />
                    <separator />
                    <menuitem action="minimize" />
                    <menuitem action="close" />
                    <menuitem action="save_and_quit" />
                    <menuitem action="quit" />
                </menu>
                <menu action="menu_edit">
                    <menuitem action="copy_page" />
                    <separator />
                    <menuitem action="edit_archive" />
                    <menuitem action="comments" />
                    <separator />
                    <menuitem action="preferences" />
                </menu>
                <menu action="menu_view">
                    <menuitem action="fullscreen" />
                    <menuitem action="double_page" />
                    <menuitem action="manga_mode" />
                    <separator />
                    <menuitem action="best_fit_mode" />
                    <menuitem action="fit_width_mode" />
                    <menuitem action="fit_height_mode" />
                    <menuitem action="fit_size_mode" />
                    <menuitem action="fit_manual_mode" />
                    <separator />
                    <menuitem action="slideshow" />
                    <separator />
                    <menuitem action="stretch" />
                    <menuitem action="invert_scroll" />
                    <menuitem action="lens" />
                    <menu action="menu_zoom">
                        <menuitem action="zoom_in" />
                        <menuitem action="zoom_out" />
                        <menuitem action="zoom_original" />
                    </menu>
                    <separator />
                    <menu action="menu_toolbars">
                        <menuitem action="menubar" />
                        <menuitem action="toolbar" />
                        <menuitem action="statusbar" />
                        <menuitem action="scrollbar" />
                        <menuitem action="thumbnails" />
                        <separator />
                        <menuitem action="hide all" />
                    </menu>
                </menu>
                <menu action="menu_go">
                    <menuitem action="next_page" />
                    <menuitem action="previous_page" />
                    <menuitem action="go_to" />
                    <menuitem action="first_page" />
                    <menuitem action="last_page" />
                    <separator />
                    <menuitem action="next_archive" />
                    <menuitem action="previous_archive" />
                    <separator />
                    <menuitem action="next_directory" />
                    <menuitem action="previous_directory" />
                </menu>
                <menu action="menu_bookmarks">
                </menu>
                <menu action="menu_tools">
                    <menuitem action="enhance_image" />
                    <menu action="menu_transform">
                        <menuitem action="rotate_90" />
                        <menuitem action="rotate_270" />
                        <menuitem action="rotate_180" />
                        <separator />
                        <menu action="menu_autorotate">
                            <menuitem action="no_autorotation" />
                            <separator />
                            <menuitem action="menu_autorotate_height" />
                            <separator />
                            <menuitem action="rotate_90_height" />
                            <menuitem action="rotate_270_height" />
                            <separator />
                            <menuitem action="menu_autorotate_width" />
                            <separator />
                            <menuitem action="rotate_90_width" />
                            <menuitem action="rotate_270_width" />
                        </menu>
                        <separator />
                        <menuitem action="flip_horiz" />
                        <menuitem action="flip_vert" />
                        <separator />
                        <menuitem action="keep_transformation" />
                    </menu>
                </menu>
                <menu action="menu_help">
                    <menuitem action="about" />
                </menu>
            </menubar>

            <popup name="Popup">
                <menu action="menu_go_popup">
                    <menuitem action="next_page" />
                    <menuitem action="previous_page" />
                    <menuitem action="go_to" />
                    <menuitem action="first_page" />
                    <menuitem action="last_page" />
                    <separator />
                    <menuitem action="next_archive" />
                    <menuitem action="previous_archive" />
                    <separator />
                    <menuitem action="next_directory" />
                    <menuitem action="previous_directory" />
                </menu>
                <menu action="menu_view_popup">
                    <menuitem action="fullscreen" />
                    <menuitem action="double_page" />
                    <menuitem action="manga_mode" />
                    <separator />
                    <menuitem action="best_fit_mode" />
                    <menuitem action="fit_width_mode" />
                    <menuitem action="fit_height_mode" />
                    <menuitem action="fit_size_mode" />
                    <menuitem action="fit_manual_mode" />
                    <separator />
                    <menuitem action="slideshow" />
                    <separator />
                    <menuitem action="enhance_image" />
                    <separator />
                    <menuitem action="stretch" />
                    <menuitem action="invert_scroll" />
                    <menuitem action="lens" />
                    <menu action="menu_zoom">
                        <menuitem action="zoom_in" />
                        <menuitem action="zoom_out" />
                        <menuitem action="zoom_original" />
                    </menu>
                    <separator />
                    <menu action="menu_toolbars">
                        <menuitem action="menubar" />
                        <menuitem action="toolbar" />
                        <menuitem action="statusbar" />
                        <menuitem action="scrollbar" />
                        <menuitem action="thumbnails" />
                        <separator />
                        <menuitem action="hide all" />
                    </menu>
                </menu>
                <menu action="menu_bookmarks_popup">
                </menu>
                <separator />
                <menuitem action="open" />
                <menu action="menu_recent" />
                <menuitem action="library" />
                <separator />
                <menuitem action="preferences" />
                <separator />
                <menuitem action="minimize" />
                <menuitem action="close" />
                <menuitem action="quit" />
            </popup>
        </ui>
        """

        self.add_ui_from_string(ui_description)
        self.insert_action_group(self._actiongroup, 0)

        self.bookmarks = bookmark_menu.BookmarksMenu(self, window)
        self.get_widget('/Menu/menu_bookmarks').set_submenu(self.bookmarks)
        self.get_widget('/Menu/menu_bookmarks').show()

        self.bookmarks_popup = bookmark_menu.BookmarksMenu(self, window)
        self.get_widget('/Popup/menu_bookmarks_popup').set_submenu(self.bookmarks_popup)
        self.get_widget('/Popup/menu_bookmarks_popup').show()

        self.recent = recent.RecentFilesMenu(self, window)
        self.get_widget('/Menu/menu_file/menu_recent').set_submenu(self.recent)
        self.get_widget('/Menu/menu_file/menu_recent').show()

        self.recentPopup = recent.RecentFilesMenu(self, window)
        self.get_widget('/Popup/menu_recent').set_submenu(self.recentPopup)
        self.get_widget('/Popup/menu_recent').show()

        openwith = openwith_menu.OpenWithMenu(self, window)
        self.get_widget('/Menu/menu_file/menu_open_with').set_submenu(openwith)
        self.get_widget('/Menu/menu_file/menu_open_with').show()

        # Load keyboard accelerator map
        if os.path.isfile(constants.KEYBINDINGS_PATH):
            gtk.accel_map_load(constants.KEYBINDINGS_PATH)
        window.add_accel_group(self.get_accel_group())

        # Is there no built-in way to do this?
        self.get_widget('/Tool/expander').set_expand(True)
        self.get_widget('/Tool/expander').set_sensitive(False)

    def set_sensitivities(self):
        """Sets the main UI's widget's sensitivities appropriately."""
        general = ('properties',
                   'edit_archive',
                   'extract_page',
                   'save_and_quit',
                   'close',
                   'delete',
                   'copy_page',
                   'slideshow',
                   'rotate_90',
                   'rotate_180',
                   'rotate_270',
                   'flip_horiz',
                   'flip_vert',
                   'next_page',
                   'previous_page',
                   'first_page',
                   'last_page',
                   'go_to',
                   'refresh_archive',
                   'next_archive',
                   'previous_archive',
                   'next_directory',
                   'previous_directory',
                   'keep_transformation',
                   'enhance_image')

        unavailable_file = ('next_archive',
                              'previous_archive',
                              'next_directory',
                              'previous_directory')
        comment = ('comments',)

        general_sensitive = False
        comment_sensitive = False

        if self._window.filehandler.file_loaded:
            general_sensitive = True

            if self._window.filehandler.get_number_of_comments():
                comment_sensitive = True

        for name in general:
            self._actiongroup.get_action(name).set_sensitive(general_sensitive)

        for name in comment:
            self._actiongroup.get_action(name).set_sensitive(comment_sensitive)

        if self._window.filehandler.file_load_failed:
            for name in unavailable_file:
                self._actiongroup.get_action(name).set_sensitive(True)

        self.bookmarks.set_sensitive(general_sensitive)
        self.bookmarks_popup.set_sensitive(general_sensitive)

# vim: expandtab:sw=4:ts=4
