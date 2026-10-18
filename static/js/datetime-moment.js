/**
 * This plug-in for DataTables represents the ultimate option in extensibility
 * for sorting date / time strings correctly. It uses
 * [Moment.js](http://momentjs.com) to create automatic type detection and
 * sorting plug-ins for DataTables based on a given format. This way, DataTables
 * will automatically detect your temporal information and sort it correctly.
 *
 * For usage instructions, please see the DataTables blog
 * post that [introduces it](//datatables.net/blog/2014-12-18).
 *
 * @name Ultimate Date / Time sorting
 * @summary Sort date and time in any format using Moment.js
 * @author [Allan Jardine](//datatables.net)
 * @depends DataTables 1.10+, Moment.js 1.7+
 *
 * @example
 *    jQuery.fn.dataTable.moment( 'HH:mm MMM D, YY' );
 *    jQuery.fn.dataTable.moment( 'dddd, MMMM Do, YYYY' );
 *
 *    $('#example').DataTable();
 */

(function (factory) {
  if (typeof define === 'function' && define.amd) {
    define(['jquery', 'moment', 'datatables.net'], factory);
  } else {
    if (typeof jQuery === 'undefined' || typeof moment === 'undefined' || !jQuery.fn || !jQuery.fn.dataTable) {
      return;
    }
    factory(jQuery, moment);
  }
})(function (jQuery, moment) {
  jQuery.fn.dataTable.moment = function (format, locale, reverseEmpties) {
    var types = jQuery.fn.dataTable.ext.type;

    // Add type detection
    types.detect.unshift(function (d) {
      if (d) {
        // Strip HTML tags and newline characters if possible
        if (d.replace) {
          d = d.replace(/(<.*?>)|(\r?\n|\r)/g, '');
        }

        // Strip out surrounding white space
        d = jQuery.trim(d);
      }

      // Null and empty values are acceptable
      if (d === '' || d === null) {
        return 'moment-' + format;
      }

      return moment(d, format, locale, true).isValid() ? 'moment-' + format : null;
    });

    // Add sorting method - use an integer for the sorting
    types.order['moment-' + format + '-pre'] = function (d) {
      if (d) {
        // Strip HTML tags and newline characters if possible
        if (d.replace) {
          d = d.replace(/(<.*?>)|(\r?\n|\r)/g, '');
        }

        // Strip out surrounding white space
        d = jQuery.trim(d);
      }

      return !moment(d, format, locale, true).isValid() ? (reverseEmpties ? -Infinity : Infinity) : parseInt(moment(d, format, locale, true).format('x'), 10);
    };
  };
});
