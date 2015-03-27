"""main.py - Main window."""

import os
import shutil
import threading
import gtk
import gobject

from mcomix import constants
from mcomix import cursor_handler
from mcomix import i18n
from mcomix import icons
from mcomix import enhance_backend
from mcomix import event
from mcomix import file_handler
from mcomix import image_handler
from mcomix import image_tools
from mcomix import lens
from mcomix import preferences
from mcomix.preferences import prefs
from mcomix import ui
from mcomix import slideshow
from mcomix import status
from mcomix import thumbbar
from mcomix import clipboard
from mcomix import pageselect
from mcomix import osd
from mcomix import keybindings
from mcomix import zoom
from mcomix import bookmark_backend
from mcomix import message_dialog
from mcomix import callback
from mcomix.library import backend, main_dialog
from mcomix import tools
from mcomix import layout
from mcomix import log
import math
import operator


class MainWindow(gtk.Window):

    """The main window, is created at start and terminates the
    program when closed.
    """

    def __init__(self, fullscreen=False, is_slideshow=slideshow,
            show_library=False, manga_mode=False, double_page=False,
            zoom_mode=None, open_path=None, open_page=1):
        super(MainWindow, self).__init__(gtk.WINDOW_TOPLEVEL)

        # ----------------------------------------------------------------
        # Attributes
        # ----------------------------------------------------------------
        self.is_fullscreen = False
        self.is_manga_mode = False
        self.is_virtual_double_page = False  # I.e. a wide image is displayed
        self.width = None
        self.height = None
        self.was_out_of_focus = False
        #: Used to remember if changing to fullscreen enabled 'Hide all'
        self.hide_all_forced = False

        self.layout = _dummy_layout()
        self._spacing = 2
        self._waiting_for_redraw = False

        self._image_box = gtk.HBox(False, 2) # XXX transitional(kept for osd.py)
        self._main_layout = gtk.Layout()
        self._event_handler = event.EventHandler(self)
        self._vadjust = self._main_layout.get_vadjustment()
        self._hadjust = self._main_layout.get_hadjustment()
        self._scroll = (gtk.HScrollbar(self._hadjust),
            gtk.VScrollbar(self._vadjust))

        self.filehandler = file_handler.FileHandler(self)
        self.filehandler.file_closed += self._on_file_closed
        self.filehandler.file_opened += self._on_file_opened
        self.imagehandler = image_handler.ImageHandler(self)
        self.imagehandler.page_available += self._page_available
        self.thumbnailsidebar = thumbbar.ThumbnailSidebar(self)

        self.statusbar = status.Statusbar()
        self.clipboard = clipboard.Clipboard(self)
        self.slideshow = slideshow.Slideshow(self)
        self.cursor_handler = cursor_handler.CursorHandler(self)
        self.enhancer = enhance_backend.ImageEnhancer(self)
        self.lens = lens.MagnifyingLens(self)
        self.osd = osd.OnScreenDisplay(self)
        self.zoom = zoom.ZoomModel()
        self.uimanager = ui.MainUI(self)
        self.menubar = self.uimanager.get_widget('/Menu')
        self.toolbar = self.uimanager.get_widget('/Tool')
        self.popup = self.uimanager.get_widget('/Popup')
        self.actiongroup = self.uimanager.get_action_groups()[0]

        self.images = [gtk.Image(), gtk.Image()] # XXX limited to at most 2 pages

        # ----------------------------------------------------------------
        # Setup
        # ----------------------------------------------------------------
        self.set_title(constants.APPNAME)
        self.set_size_request(300, 300)  # Avoid making the window *too* small
        self.resize(prefs['window width'], prefs['window height'])

        # Hook up keyboard shortcuts
        self._event_handler.register_key_events()

        # This is a hack to get the focus away from the toolbar so that
        # we don't activate it with space or some other key (alternative?)
        self.toolbar.set_focus_child(
            self.uimanager.get_widget('/Tool/expander'))
        self.toolbar.set_style(gtk.TOOLBAR_ICONS)
        self.toolbar.set_icon_size(gtk.ICON_SIZE_LARGE_TOOLBAR)

        for img in self.images:
            self._main_layout.put(img, 0, 0)
        self.set_bg_colour(prefs['bg colour'])

        self._vadjust.step_increment = 15
        self._vadjust.page_increment = 1
        self._hadjust.step_increment = 15
        self._hadjust.page_increment = 1

        table = gtk.Table(2, 2, False)
        table.attach(self.thumbnailsidebar, 0, 1, 2, 5, gtk.FILL,
            gtk.FILL|gtk.EXPAND, 0, 0)

        table.attach(self._main_layout, 1, 2, 2, 3, gtk.FILL|gtk.EXPAND,
            gtk.FILL|gtk.EXPAND, 0, 0)
        table.attach(self._scroll[constants.HEIGHT_AXIS], 2, 3, 2, 3, gtk.FILL|gtk.SHRINK,
            gtk.FILL|gtk.SHRINK, 0, 0)
        table.attach(self._scroll[constants.WIDTH_AXIS], 1, 2, 4, 5, gtk.FILL|gtk.SHRINK,
            gtk.FILL, 0, 0)
        table.attach(self.menubar, 0, 3, 0, 1, gtk.FILL|gtk.SHRINK,
            gtk.FILL, 0, 0)
        table.attach(self.toolbar, 0, 3, 1, 2, gtk.FILL|gtk.SHRINK,
            gtk.FILL, 0, 0)
        table.attach(self.statusbar, 0, 3, 5, 6, gtk.FILL|gtk.SHRINK,
            gtk.FILL, 0, 0)

        if prefs['default double page'] or double_page:
            self.actiongroup.get_action('double_page').activate()

        if prefs['default manga mode'] or manga_mode:
            self.actiongroup.get_action('manga_mode').activate()

        # Determine zoom mode. If zoom_mode is passed, it overrides
        # the zoom mode preference.
        zoom_actions = { constants.ZOOM_MODE_BEST : 'best_fit_mode',
                constants.ZOOM_MODE_WIDTH : 'fit_width_mode',
                constants.ZOOM_MODE_HEIGHT : 'fit_height_mode',
                constants.ZOOM_MODE_SIZE : 'fit_size_mode',
                constants.ZOOM_MODE_MANUAL : 'fit_manual_mode' }

        if zoom_mode is not None:
            zoom_action = zoom_actions[zoom_mode]
        else:
            zoom_action = zoom_actions[prefs['zoom mode']]

        if zoom_action == 'fit_manual_mode':
            # This little ugly hack is to get the activate call on
            # 'fit_manual_mode' to actually create an event (and callback).
            # Since manual mode is the default selected radio button action
            # it won't send an event if we activate it when it is already
            # the selected one.
            self.actiongroup.get_action('best_fit_mode').activate()

        self.actiongroup.get_action(zoom_action).activate()

        if prefs['stretch']:
            self.actiongroup.get_action('stretch').activate()

        if prefs['invert smart scroll']:
            self.actiongroup.get_action('invert_scroll').activate()

        if prefs['keep transformation']:
            prefs['keep transformation'] = False
            self.actiongroup.get_action('keep_transformation').activate()
        else:
            prefs['rotation'] = 0
            prefs['vertical flip'] = False
            prefs['horizontal flip'] = False

        self._toggle_controls = (
            ('toolbar'   , 'show toolbar'   , self.toolbar         ),
            ('menubar'   , 'show menubar'   , self.menubar         ),
            ('statusbar' , 'show statusbar' , self.statusbar       ),
            ('scrollbar' , 'show scrollbar' , None                 ),
            ('thumbnails', 'show thumbnails', self.thumbnailsidebar),
        )

        # Start with all widgets hidden to avoid ugly transitions.
        for action, control, widget in self._toggle_controls:
            if widget is not None:
                widget.hide()

        toggleaction = self.actiongroup.get_action('hide_all')
        toggleaction.set_active(prefs['hide all'])

        for action, control, widget in self._toggle_controls:
            toggleaction = self.actiongroup.get_action(action)
            toggleaction.set_active(prefs[control])

        self.actiongroup.get_action('menu_autorotate_width').set_sensitive(False)
        self.actiongroup.get_action('menu_autorotate_height').set_sensitive(False)

        self.add(table)
        table.show()
        self._main_layout.show()

        self._main_layout.set_events(gtk.gdk.BUTTON1_MOTION_MASK |
                                     gtk.gdk.BUTTON2_MOTION_MASK |
                                     gtk.gdk.BUTTON_PRESS_MASK |
                                     gtk.gdk.BUTTON_RELEASE_MASK |
                                     gtk.gdk.POINTER_MOTION_MASK)

        self._main_layout.drag_dest_set(gtk.DEST_DEFAULT_ALL,
                                        [('text/uri-list', 0, 0)],
                                        gtk.gdk.ACTION_COPY |
                                        gtk.gdk.ACTION_MOVE)

        self.connect('focus-in-event', self.gained_focus)
        self.connect('focus-out-event', self.lost_focus)
        self.connect('delete_event', self.close_program)
        self.connect('key_press_event', self._event_handler.key_press_event)
        self.connect('key_release_event', self._event_handler.key_release_event)
        self.connect('configure_event', self._event_handler.resize_event)

        self._main_layout.connect('button_release_event',
            self._event_handler.mouse_release_event)
        self._main_layout.connect('scroll_event',
            self._event_handler.scroll_wheel_event)
        self._main_layout.connect('button_press_event',
            self._event_handler.mouse_press_event)
        self._main_layout.connect('motion_notify_event',
            self._event_handler.mouse_move_event)
        self._main_layout.connect('drag_data_received',
            self._event_handler.drag_n_drop_event)

        self.uimanager.set_sensitivities()
        self.show()

        # If MComix is set to start in fullscreen mode, it
        # cannot switch to windowed mode on Win32 unless this
        # condition is set to trigger after normal show().
        if prefs['default fullscreen'] or fullscreen:
            self.actiongroup.get_action('fullscreen').activate()

        if prefs['previous quit was quit and save']:
            fileinfo = self.filehandler.read_fileinfo_file()

            if fileinfo != None:

                open_path = fileinfo[0]
                open_page = fileinfo[1] + 1

        prefs['previous quit was quit and save'] = False

        if open_path is not None:
            self.filehandler.open_file(open_path)

        if is_slideshow:
            self.actiongroup.get_action('slideshow').activate()

        if show_library:
            self.actiongroup.get_action('library').activate()

        self.cursor_handler.auto_hide_on()
        # Make sure we receive *all* mouse motion events,
        # even if a modal dialog is being shown.
        def _on_event(event):
            if gtk.gdk.MOTION_NOTIFY == event.type:
                self.cursor_handler.refresh()
            gtk.main_do_event(event)
        gtk.gdk.event_handler_set(_on_event)

    def gained_focus(self, *args):
        self.was_out_of_focus = False

    def lost_focus(self, *args):
        self.was_out_of_focus = True

        # If the user presses CTRL for a keyboard shortcut, e.g. to
        # open the library, key_release_event isn't fired and force_single_step
        # isn't properly unset.
        self.imagehandler.force_single_step = False

    def draw_image(self, at_bottom=False, scroll=False):
        """Draw the current pages and update the titlebar and statusbar.
        """
        if not self._waiting_for_redraw:  # Don't stack up redraws.
            self._waiting_for_redraw = True
            gobject.idle_add(self._draw_image, at_bottom, scroll,
                priority=gobject.PRIORITY_HIGH_IDLE)

    def _update_control_visibility(self, control, toggleaction=None, redraw=True):
        """Called to update a control visibilty."""
        if toggleaction is not None:
            prefs[control] = toggleaction.get_active()
        if 'hide all' == control:
            hide_all = prefs[control]
            for action, sub_control, widget in self._toggle_controls:
                self.actiongroup.get_action(action).set_sensitive(not hide_all)
                self._update_control_visibility(sub_control, redraw=False)
            if hide_all:
                self._scroll[constants.HEIGHT_AXIS].hide()
                self._scroll[constants.WIDTH_AXIS].hide()
        else:
            enabled = not prefs['hide all']
            enabled &= prefs[control]
            if 'show toolbar' == control:
                widget = self.toolbar
            elif 'show statusbar' == control:
                widget = self.statusbar
            elif 'show menubar' == control:
                widget = self.menubar
            elif 'show thumbnails' == control:
                widget = self.thumbnailsidebar
                enabled &= self.filehandler.file_loaded
                enabled &= self.imagehandler.get_number_of_pages() > 0
            else:
                widget = None
            if widget is not None:
                if enabled == widget.get_visible():
                    # No change in visibility!
                    redraw = False
                else:
                    (widget.show if enabled else widget.hide)()

        if redraw:
            # Since the size of the drawing area is dependent
            # on the visible controls, redraw the page.
            self.draw_image()

    def _draw_image(self, at_bottom, scroll):

        if not self.filehandler.file_loaded:
            self._waiting_for_redraw = False
            return False

        self.is_virtual_double_page = self.imagehandler.get_virtual_double_page()

        if self.imagehandler.page_is_available():
            distribution_axis = constants.DISTRIBUTION_AXIS
            alignment_axis = constants.ALIGNMENT_AXIS
            pixbuf_count = 2 if self.displayed_double() else 1 # XXX limited to at most 2 pages
            pixbuf_list = list(self.imagehandler.get_pixbufs(pixbuf_count))
            size_list = [[pixbuf.get_width(), pixbuf.get_height()]
                         for pixbuf in pixbuf_list]

            if self.is_manga_mode:
                orientation = constants.MANGA_ORIENTATION
            else:
                orientation = constants.WESTERN_ORIENTATION

            # Rotation handling:
            # - apply Exif rotation on individual images
            # - apply automatic rotation (size based) on whole page
            # - apply manual rotation on whole page
            if prefs['auto rotate from exif']:
                rotation_list = [image_tools.get_implied_rotation(pixbuf)
                                 for pixbuf in pixbuf_list]
            else:
                rotation_list = [0] * len(pixbuf_list)
            virtual_size = [0, 0]
            for i in range(pixbuf_count):
                if rotation_list[i] in (90, 270):
                    size_list[i].reverse()
                size = size_list[i]
                virtual_size[distribution_axis] += size[distribution_axis]
                virtual_size[alignment_axis] = max(virtual_size[alignment_axis],
                                                   size[alignment_axis])
            rotation = self._get_size_rotation(*virtual_size)
            rotation = (rotation + prefs['rotation']) % 360
            if rotation in (90, 270):
                distribution_axis, alignment_axis = alignment_axis, distribution_axis
                orientation = list(orientation)
                orientation.reverse()
                for i in range(pixbuf_count):
                    size_list[i].reverse()
            if rotation in (180, 270):
                orientation = tools.vector_opposite(orientation)
            for i in range(pixbuf_count):
                rotation_list[i] = (rotation_list[i] + rotation) % 360

            viewport_size = () # dummy
            expand_area = False
            scrollbar_requests = [False] * len(self._scroll)
            # Visible area size is recomputed depending on scrollbar visibility
            while True:
                self._show_scrollbars(scrollbar_requests)
                new_viewport_size = self.get_visible_area_size()
                if new_viewport_size == viewport_size:
                    break
                viewport_size = new_viewport_size
                zoom_dummy_size = list(viewport_size)
                dasize = zoom_dummy_size[distribution_axis] - \
                    self._spacing * (pixbuf_count - 1)
                if dasize <= 0:
                    dasize = 1
                zoom_dummy_size[distribution_axis] = dasize
                scaled_sizes = self.zoom.get_zoomed_size(size_list, zoom_dummy_size,
                    distribution_axis)
                self.layout = layout.FiniteLayout(scaled_sizes,
                                                  viewport_size,
                                                  orientation,
                                                  self._spacing,
                                                  expand_area,
                                                  distribution_axis,
                                                  alignment_axis)
                union_scaled_size = self.layout.get_union_box().get_size()
                scrollbar_requests = map(operator.or_, scrollbar_requests,
                    tools.smaller(viewport_size, union_scaled_size))
                if len(filter(None, scrollbar_requests)) > 1 and not expand_area:
                    expand_area = True
                    viewport_size = () # start anew

            for i in range(pixbuf_count):
                pixbuf_list[i] = image_tools.fit_pixbuf_to_rectangle(
                    pixbuf_list[i], scaled_sizes[i], rotation_list[i])

            for i in range(pixbuf_count):
                if prefs['horizontal flip']: # 2D only
                    pixbuf_list[i] = pixbuf_list[i].flip(horizontal=True)
                if prefs['vertical flip']: # 2D only
                    pixbuf_list[i] = pixbuf_list[i].flip(horizontal=False)
                pixbuf_list[i] = self.enhancer.enhance(pixbuf_list[i])

            for i in range(pixbuf_count):
                self.images[i].set_from_pixbuf(pixbuf_list[i])

            scales = tuple(map(lambda x, y: math.sqrt(tools.div(
                tools.volume(x), tools.volume(y))), scaled_sizes, size_list))

            resolutions = tuple(map(lambda x, y: x + [y,], size_list, scales))
            if self.is_manga_mode:
                resolutions = tuple(reversed(resolutions))
            self.statusbar.set_resolution(resolutions)
            self.statusbar.update()

            smartbg = prefs['smart bg']
            smartthumbbg = prefs['smart thumb bg'] and prefs['show thumbnails']
            if smartbg or smartthumbbg:
                bg_colour = self.imagehandler.get_pixbuf_auto_background(pixbuf_count)
            if smartbg:
                self.set_bg_colour(bg_colour)
            if smartthumbbg:
                self.thumbnailsidebar.change_thumbnail_background_color(bg_colour)

            #self._image_box.window.freeze_updates() # XXX replacement necessary?
            self._main_layout.set_size(*union_scaled_size)
            content_boxes = self.layout.get_content_boxes()
            for i in range(pixbuf_count):
                self._main_layout.move(self.images[i],
                    *content_boxes[i].get_position())

            for i in range(pixbuf_count):
                self.images[i].show()
            for i in range(pixbuf_count, len(self.images)):
                self.images[i].hide()

            # Reset orientation so scrolling behaviour is sane.
            if self.is_manga_mode:
                self.layout.set_orientation(constants.MANGA_ORIENTATION)
            else:
                self.layout.set_orientation(constants.WESTERN_ORIENTATION)

            if scroll:
                if at_bottom:
                    self.scroll_to_predefined((constants.SCROLL_TO_END,) * 2,
                        constants.LAST_INDEX)
                else:
                    self.scroll_to_predefined((constants.SCROLL_TO_START,) * 2,
                        constants.FIRST_INDEX)

            #self._image_box.window.thaw_updates() # XXX replacement necessary?
        else:
            # If the pixbuf for the current page(s) isn't available,
            # hide all images to clear any old pixbufs.
            # XXX How about calling self._clear_main_area?
            for i in range(len(self.images)):
                self.images[i].hide()

        self._waiting_for_redraw = False

        return False

    def _update_page_information(self):
        """ Updates the window with information that can be gathered
        even when the page pixbuf(s) aren't ready yet. """

        page_number = self.imagehandler.get_current_page()
        if not page_number:
            return
        if self.displayed_double():
            number_of_pages = 2
            left_filename, right_filename = self.imagehandler.get_page_filename(double=True)
            if self.is_manga_mode:
                left_filename, right_filename = right_filename, left_filename
            filename = left_filename + ', ' + right_filename
        else:
            number_of_pages = 1
            filename = self.imagehandler.get_page_filename()
        self.statusbar.set_page_number(page_number,
                                       self.imagehandler.get_number_of_pages(),
                                       number_of_pages)
        self.statusbar.set_filename(filename)
        self.statusbar.set_root(self.filehandler.get_base_filename())
        self.statusbar.update()
        self.update_title()

    def _get_size_rotation(self, width, height):
        """ Determines the rotation to be applied.
        Returns the degree of rotation (0, 90, 180, 270). """

        size_rotation = 0

        if (height > width and
            prefs['auto rotate depending on size'] in
                (constants.AUTOROTATE_HEIGHT_90, constants.AUTOROTATE_HEIGHT_270)):

            if prefs['auto rotate depending on size'] == constants.AUTOROTATE_HEIGHT_90:
                size_rotation = 90
            else:
                size_rotation = 270
        elif (width > height and
              prefs['auto rotate depending on size'] in
                (constants.AUTOROTATE_WIDTH_90, constants.AUTOROTATE_WIDTH_270)):

            if prefs['auto rotate depending on size'] == constants.AUTOROTATE_WIDTH_90:
                size_rotation = 90
            else:
                size_rotation = 270

        return size_rotation

    def _page_available(self, page):
        """ Called whenever a new page is ready for displaying. """
        # Refresh display when currently opened page becomes available.
        if page == self.imagehandler.get_current_page() \
            or (self.displayed_double() and page == self.imagehandler.get_current_page() + 1):

            self.draw_image(False, True)

        # Use first page as application icon when opening archives.
        if (page == 1
            and self.filehandler.archive_type is not None
            and prefs['archive thumbnail as icon']):
            pixbuf = self.imagehandler.get_thumbnail(page, 48, 48)
            self.set_icon(pixbuf)

    def _on_file_opened(self):
        self.uimanager.set_sensitivities()
        number, count = self.filehandler.get_file_number()
        self.statusbar.set_file_number(number, count)
        self.statusbar.update()

    def _on_file_closed(self):
        self.clear()
        self.thumbnailsidebar.hide()
        self.thumbnailsidebar.clear()
        self.uimanager.set_sensitivities()
        self.set_icon_list(*icons.mcomix_icons())

    def new_page(self, at_bottom=False):
        """Draw a *new* page correctly (as opposed to redrawing the same
        image with a new size or whatever).
        """
        if not prefs['keep transformation']:
            prefs['rotation'] = 0
            prefs['horizontal flip'] = False
            prefs['vertical flip'] = False

        self.draw_image(at_bottom=at_bottom, scroll=True)

    @callback.Callback
    def page_changed(self):
        """ Called on page change. """
        self._update_control_visibility('show thumbnails', redraw=False)
        self.thumbnailsidebar.load_thumbnails()
        self._update_page_information()

    def set_page(self, num, at_bottom=False):
        if num == self.imagehandler.get_current_page():
            return
        self.imagehandler.set_page(num)
        self.page_changed()
        self.new_page(at_bottom=at_bottom)
        self.slideshow.update_delay()

    def next_book(self):
        archive_open = self.filehandler.archive_type is not None
        next_archive_opened = False
        if (self.slideshow.is_running() and \
            prefs['slideshow can go to next archive']) or \
           prefs['auto open next archive']:
            next_archive_opened = self.filehandler._open_next_archive()

        # If "Auto open next archive" is disabled, do not go to the next
        # directory if current file was an archive.
        if not next_archive_opened and \
           prefs['auto open next directory'] and \
           (not archive_open or prefs['auto open next archive']):
            self.filehandler.open_next_directory()

    def previous_book(self):
        archive_open = self.filehandler.archive_type is not None
        previous_archive_opened = False
        if (self.slideshow.is_running() and \
            prefs['slideshow can go to next archive']) or \
            prefs['auto open next archive']:
            previous_archive_opened = self.filehandler._open_previous_archive()

        # If "Auto open next archive" is disabled, do not go to the previous
        # directory if current file was an archive.
        if not previous_archive_opened and \
            prefs['auto open next directory'] and \
            (not archive_open or prefs['auto open next archive']):
            self.filehandler.open_previous_directory()

    def flip_page(self, step, single_step=False):

        if not self.filehandler.file_loaded:
            if -1 == step:
                self.previous_book()
            elif 1 == step:
                self.next_book()
            return

        current_page = self.imagehandler.get_current_page()
        number_of_pages = self.imagehandler.get_number_of_pages()

        new_page = current_page + step
        if (1 == abs(step) and
            not single_step and
            prefs['default double page'] and
            prefs['double step in double page mode']):
            if +1 == step and not self.imagehandler.get_virtual_double_page():
                new_page += 1
            elif -1 == step and not self.imagehandler.get_virtual_double_page(new_page):
                new_page -= 1

        if new_page <= 0:
            if -1 == step:
                return self.previous_book()
            # Handle empty archive case.
            new_page = min(1, number_of_pages)
        elif new_page > number_of_pages:
            if 1 == step:
                return self.next_book()
            new_page = number_of_pages

        if new_page != current_page:
            self.set_page(new_page, at_bottom=(-1 == step))

    def first_page(self):
        number_of_pages = self.imagehandler.get_number_of_pages()
        if number_of_pages:
            self.set_page(1)

    def last_page(self):
        number_of_pages = self.imagehandler.get_number_of_pages()
        if number_of_pages:
            self.set_page(number_of_pages)

    def page_select(self, *args):
        pageselect.Pageselector(self)

    def rotate_90(self, *args):
        prefs['rotation'] = (prefs['rotation'] + 90) % 360
        self.draw_image()

    def rotate_180(self, *args):
        prefs['rotation'] = (prefs['rotation'] + 180) % 360
        self.draw_image()

    def rotate_270(self, *args):
        prefs['rotation'] = (prefs['rotation'] + 270) % 360
        self.draw_image()

    def flip_horizontally(self, *args):
        prefs['horizontal flip'] = not prefs['horizontal flip']
        self.draw_image()

    def flip_vertically(self, *args):
        prefs['vertical flip'] = not prefs['vertical flip']
        self.draw_image()

    def change_double_page(self, toggleaction):
        prefs['default double page'] = toggleaction.get_active()
        self._update_page_information()
        self.draw_image()

    def change_manga_mode(self, toggleaction):
        prefs['default manga mode'] = toggleaction.get_active()
        self.is_manga_mode = toggleaction.get_active()
        self.draw_image()

    def change_invert_scroll(self, toggleaction):
        prefs['invert smart scroll'] = toggleaction.get_active()

    def change_fullscreen(self, toggleaction):
        self.is_fullscreen = toggleaction.get_active()
        if self.is_fullscreen:
            self.fullscreen()

            if (prefs['hide all in fullscreen'] and
                not prefs['hide all']):

                self.hide_all_forced = True
                prefs['hide all'] = True
                self._update_control_visibility('hide all', redraw=False)
        else:
            self.unfullscreen()

            if (prefs['hide all in fullscreen'] and
                prefs['hide all'] and
                self.hide_all_forced):

                self.hide_all_forced = False
                prefs['hide all'] = False
                self._update_control_visibility('hide all', redraw=False)

    def change_zoom_mode(self, radioaction=None, *args):
        if radioaction:
            prefs['zoom mode'] = radioaction.get_current_value()

        self.zoom.set_fit_mode(prefs['zoom mode'])
        self.zoom.set_scale_up(prefs['stretch'])
        self.zoom.reset_user_zoom()
        self.draw_image()

    def change_autorotation(self, radioaction=None, *args):
        """ Switches between automatic rotation modes, depending on which
        radiobutton is currently activated. """
        if radioaction:
            prefs['auto rotate depending on size'] = radioaction.get_current_value()

        self.draw_image()

    def change_stretch(self, toggleaction, *args):
        """ Toggles stretching small images. """
        prefs['stretch'] = toggleaction.get_active()
        self.zoom.set_scale_up(prefs['stretch'])
        self.draw_image()

    def change_toolbar_visibility(self, toggleaction):
        self._update_control_visibility('show toolbar', toggleaction)

    def change_menubar_visibility(self, toggleaction):
        self._update_control_visibility('show menubar', toggleaction)

    def change_statusbar_visibility(self, toggleaction):
        self._update_control_visibility('show statusbar', toggleaction)

    def change_scrollbar_visibility(self, toggleaction):
        self._update_control_visibility('show scrollbar', toggleaction)

    def change_thumbnails_visibility(self, toggleaction):
        self._update_control_visibility('show thumbnails', toggleaction)

    def change_hide_all(self, toggleaction):
        self._update_control_visibility('hide all', toggleaction)

    def change_keep_transformation(self, *args):
        prefs['keep transformation'] = not prefs['keep transformation']

    def manual_zoom_in(self, *args):
        self.zoom.zoom_in()
        self.draw_image()

    def manual_zoom_out(self, *args):
        self.zoom.zoom_out()
        self.draw_image()

    def manual_zoom_original(self, *args):
        self.zoom.reset_user_zoom()
        self.draw_image()

    def _show_scrollbars(self, request):
        """ Enables scroll bars depending on requests and preferences. """

        limit = prefs['show scrollbar'] and \
            not prefs['hide all'] and\
            not (self.is_fullscreen and \
            prefs['hide all in fullscreen'])
        for i in range(len(self._scroll)):
            if limit and request[i]:
                self._scroll[i].show_all()
            else:
                self._scroll[i].hide_all()

    def is_scrollable_horizontally(self):
        """ Returns True when the displayed image does not fit into the display
        port horizontally and must be scrolled to be viewed completely. """

        screen_width, _ = self.get_visible_area_size()
        left_width = self.images[0].get_pixbuf() and \
                self.images[0].get_pixbuf().get_width() or 0 # XXX transitional(double page limitation)
        right_width = self.images[1].get_pixbuf() and \
                self.images[1].get_pixbuf().get_width() or 0 # XXX transitional(double page limitation)
        image_width = max(left_width, right_width)

        return image_width > screen_width

    def is_scrollable_vertically(self):
        """ Returns True when the displayed image does not fit into the display
        port vertically and must be scrolled to be viewed completely. """

        _, screen_height = self.get_visible_area_size()
        left_height = self.images[0].get_pixbuf() and \
                self.images[0].get_pixbuf().get_height() or 0 # XXX transitional(double page limitation)
        right_height = self.images[1].get_pixbuf() and \
                self.images[1].get_pixbuf().get_height() or 0 # XXX transitional(double page limitation)
        image_height = max(left_height, right_height)

        return image_height > screen_height

    def is_scrollable(self):
        """ Returns True when either is_scrollable_horizontally or
        is_scrollable_vertically return True. """
        return self.is_scrollable_horizontally() or \
               self.is_scrollable_vertically()

    def scroll_with_flipping(self, x, y):
        """Returns true if able to scroll without flipping to
        a new page and False otherwise."""
        return self._event_handler._scroll_with_flipping(x, y)

    def scroll(self, x, y, bound=None):
        """Scroll <x> px horizontally and <y> px vertically. If <bound> is
        'first' or 'second', we will not scroll out of the first or second
        page respectively (dependent on manga mode). The <bound> argument
        only makes sense in double page mode.

        Return True if call resulted in new adjustment values, False
        otherwise.
        """
        old_hadjust = self._hadjust.get_value()
        old_vadjust = self._vadjust.get_value()

        visible_width, visible_height = self.get_visible_area_size()

        hadjust_upper = max(0, self._hadjust.upper - visible_width)
        vadjust_upper = max(0, self._vadjust.upper - visible_height)
        hadjust_lower = 0

        if bound is not None and self.is_manga_mode:
            bound = {'first': 'second', 'second': 'first'}[bound]

        if bound == 'first':
            hadjust_upper = max(0, hadjust_upper -
                self.images[1].size_request()[0] - 2) # XXX transitional(double page limitation)

        elif bound == 'second':
            hadjust_lower = self.images[0].size_request()[0] + 2 # XXX transitional(double page limitation)

        new_hadjust = old_hadjust + x
        new_vadjust = old_vadjust + y

        new_hadjust = max(hadjust_lower, new_hadjust)
        new_vadjust = max(0, new_vadjust)

        new_hadjust = min(hadjust_upper, new_hadjust)
        new_vadjust = min(vadjust_upper, new_vadjust)

        self._vadjust.set_value(new_vadjust)
        self._hadjust.set_value(new_hadjust)

        return old_vadjust != new_vadjust or old_hadjust != new_hadjust

    def scroll_to_predefined(self, destination, index=None):
        self.layout.scroll_to_predefined(destination, index)
        self.update_viewport_position()

    def update_viewport_position(self):
        viewport_position = self.layout.get_viewport_box().get_position()
        self._hadjust.set_value(viewport_position[0]) # 2D only
        self._vadjust.set_value(viewport_position[1]) # 2D only

    def update_layout_position(self):
        self.layout.set_viewport_position(
            (int(round(self._hadjust.value)), int(round(self._vadjust.value))))

    def clear(self):
        """Clear the currently displayed data (i.e. "close" the file)."""
        self._clear_main_area()
        self.set_title(constants.APPNAME)
        self.statusbar.set_message('')

    def _clear_main_area(self):
        for i in self.images:
            i.hide()
        for i in self.images:
            i.clear()
        self._show_scrollbars([False] * len(self._scroll))
        self.layout = _dummy_layout()
        self._main_layout.set_size(*self.layout.get_union_box().get_size())
        self.set_bg_colour(prefs['bg colour'])

    def displayed_double(self):
        """Return True if two pages are currently displayed."""
        return (self.imagehandler.get_current_page() and
                prefs['default double page'] and
                not self.is_virtual_double_page and
                self.imagehandler.get_current_page() != self.imagehandler.get_number_of_pages())

    def get_visible_area_size(self):
        """Return a 2-tuple with the width and height of the visible part
        of the main layout area.
        """
        width, height = self.get_size()

        if not prefs['hide all']:

            if prefs['show toolbar']:
                height -= self.toolbar.size_request()[1]

            if prefs['show statusbar']:
                height -= self.statusbar.size_request()[1]

            if prefs['show thumbnails']:
                width -= self.thumbnailsidebar.get_width()

            if prefs['show menubar']:
                height -= self.menubar.size_request()[1]

            if prefs['show scrollbar']:

                if self._scroll[constants.HEIGHT_AXIS].get_visible():
                    width -= self._scroll[constants.HEIGHT_AXIS]\
                        .size_request()[constants.WIDTH_AXIS]

                if self._scroll[constants.WIDTH_AXIS].get_visible():
                    height -= self._scroll[constants.WIDTH_AXIS]\
                        .size_request()[constants.HEIGHT_AXIS]

        # FIXME: can happen when aggressively playing with window resize...
        assert width > 0 and height > 0

        return width, height

    def get_layout_pointer_position(self):
        """Return a 2-tuple with the x and y coordinates of the pointer
        on the main layout area, relative to the layout.
        """
        x, y = self._main_layout.get_pointer()
        x += self._hadjust.get_value()
        y += self._vadjust.get_value()

        return (x, y)

    def set_cursor(self, mode):
        """Set the cursor on the main layout area to <mode>. You should
        probably use the cursor_handler instead of using this method
        directly.
        """
        self._main_layout.window.set_cursor(mode)

    def update_title(self):
        """Set the title acording to current state."""
        this_screen = 2 if self.displayed_double() else 1 # XXX limited to at most 2 pages
        # TODO introduce formatter to merge these string ops with the ops for status bar updates
        title = '['
        for i in range(this_screen):
            title += '%d' % (self.imagehandler.get_current_page() + i)
            if i < this_screen - 1:
                title += ','
        title += ' / %d]  %s' % (self.imagehandler.get_number_of_pages(),
            self.imagehandler.get_pretty_current_filename())
        title = i18n.to_unicode(title)

        if self.slideshow.is_running():
            title = '[%s] %s' % (_('SLIDESHOW'), title)

        self.set_title(title)

    def set_bg_colour(self, colour):
        """Set the background colour to <colour>. Colour is a sequence in the
        format (r, g, b). Values are 16-bit.
        """
        self._main_layout.modify_bg(gtk.STATE_NORMAL,
                                    gtk.gdk.Color(colour[0],
                                                  colour[1],
                                                  colour[2]))

        if prefs['thumbnail bg uses main colour']:
            self.thumbnailsidebar.change_thumbnail_background_color(prefs['bg colour'])
        self._bg_colour = colour

    def get_bg_colour(self):
        return self._bg_colour

    def extract_page(self, *args):
        """ Derive some sensible filename (archive name + _ + filename should do) and offer
        the user the choice to save the current page with the selected name. """
        if self.filehandler.archive_type is not None:
            archive_name = self.filehandler.get_pretty_current_filename()
            file_name = self.imagehandler.get_path_to_page()
            suggested_name = os.path.splitext(archive_name)[0] + \
                u'_' + os.path.split(file_name)[-1]
        else:
            suggested_name = os.path.split(self.imagehandler.get_path_to_page())[-1]

        save_dialog = gtk.FileChooserDialog(_('Save page as'), self,
            gtk.FILE_CHOOSER_ACTION_SAVE, (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
            gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT))
        save_dialog.set_current_name(suggested_name.encode('utf-8'))

        if save_dialog.run() == gtk.RESPONSE_ACCEPT and save_dialog.get_filename():
            shutil.copy(self.imagehandler.get_path_to_page(),
                save_dialog.get_filename().decode('utf-8'))

        save_dialog.destroy()

    def delete(self, *args):
        """ The currently opened file/archive will be deleted after showing
        a confirmation dialog. """

        current_file = self.imagehandler.get_real_path()
        dialog = message_dialog.MessageDialog(self, gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION,
                gtk.BUTTONS_NONE)
        dialog.set_should_remember_choice('delete-opend-file', (gtk.RESPONSE_OK,))
        dialog.set_text(
                _('Delete "%s"?') % os.path.basename(current_file),
                _('The file will be deleted from your harddisk.'))
        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        dialog.add_button(gtk.STOCK_DELETE, gtk.RESPONSE_OK)
        dialog.set_default_response(gtk.RESPONSE_OK)
        result = dialog.run()

        if result == gtk.RESPONSE_OK:
            # Go to next page/archive, and delete current file
            if self.filehandler.archive_type is not None:
                self.filehandler.last_read_page.clear_page(current_file)

                next_opened = self.filehandler._open_next_archive()
                if not next_opened:
                    next_opened = self.filehandler._open_previous_archive()
                if not next_opened:
                    self.filehandler.close_file()

                if os.path.isfile(current_file):
                    os.unlink(current_file)
            else:
                if self.imagehandler.get_number_of_pages() > 1:
                    # Open the next/previous file
                    if self.imagehandler.get_current_page() >= self.imagehandler.get_number_of_pages():
                        self.flip_page(-1)
                    else:
                        self.flip_page(+1)
                    # Unlink the desired file
                    if os.path.isfile(current_file):
                        os.unlink(current_file)
                    # Refresh the directory
                    self.filehandler.refresh_file()
                else:
                    self.filehandler.close_file()
                    if os.path.isfile(current_file):
                        os.unlink(current_file)

    def show_info_panel(self):
        """ Shows an OSD displaying information about the current page. """

        if not self.filehandler.file_loaded:
            return

        filename = self.imagehandler.get_pretty_current_filename().encode('utf-8')
        page_text = '%s %s' % (_('Page'), self.statusbar.get_page_number())
        if self.statusbar.get_file_number():
            page_text += ' ' + self.statusbar.get_file_number()

        self.osd.show(filename + "\n\n" + page_text)

    def minimize(self, *args):
        """ Minimizes the MComix window. """
        self.iconify()

    def write_config_files(self):

        self.filehandler.write_fileinfo_file()
        preferences.write_preferences_file()
        bookmark_backend.BookmarksStore.write_bookmarks_file()

        # Write keyboard accelerator map
        keybindings.keybinding_manager(self).save()

    def save_and_terminate_program(self, *args):
        prefs['previous quit was quit and save'] = True

        self.terminate_program()

    def close_program(self, *args):
        self.terminate_program()

    def terminate_program(self):
        """Run clean-up tasks and exit the program."""

        self.hide()

        if gtk.main_level() > 0:
            gtk.main_quit()

        if prefs['auto load last file'] and self.filehandler.file_loaded:
            prefs['path to last file'] = self.imagehandler.get_real_path()
            prefs['page of last file'] = self.imagehandler.get_current_page()

        else:
            prefs['path to last file'] = ''
            prefs['page of last file'] = 1

        if prefs['hide all'] and self.hide_all_forced and self.fullscreen:
            prefs['hide all'] = False

        self.write_config_files()

        self.filehandler.close_file()
        if main_dialog._dialog is not None:
            main_dialog._dialog.close()
        backend.LibraryBackend().close()

        # This hack is to avoid Python issue #1856.
        for thread in threading.enumerate():
            if thread is not threading.currentThread():
                log.debug('Waiting for thread %s to finish before exit', thread)
                thread.join()

#: Main window instance
__main_window = None


def main_window():
    """ Returns the global main window instance. """
    return __main_window


def set_main_window(window):
    global __main_window
    __main_window = window


def _dummy_layout():
    return layout.FiniteLayout(((1,1),), (1,1), (1,1), 0, False, 0, 0)


# vim: expandtab:sw=4:ts=4
