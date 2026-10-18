// console.log('DTGS_NONCE is enabled');
jQuery(document).ready(function () {
  jQuery(".dtsFrontendExport").each(function () {
    let link = jQuery(this).find("a.export-pdf, a.export-print, a.export-email, a.export-xls, a.export-xlsx, a.export-csv");
    if (link.length) {
      let href = link.attr("href");
      if (href) {
        href = href.replace(
          /nonce=SUPNONCEFRONTEND/,
          "nonce=" + DTGS_NONCE_FRONTEND
        );
        link.attr("href", href);
      }
    }
  });
});
