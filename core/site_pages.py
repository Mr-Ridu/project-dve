"""Content registry for the site's secondary pages.

Every page here renders through core.views.page_detail with
templates/core/page.html. The medical pages were removed with the industrial
rebrand; the registry holds the legal pages, careers and the resource pages
linked from the main navigation.
"""

PAGES = {
    'accessibility-statement': {
        'title': 'Accessibility Statement',
        'paragraphs': [
            'Accessibility Statement. Last updated: November 2, 2026. Techno Mate Technologies is committed to ensuring digital accessibility for all individuals.',
            'We have voluntarily undertaken efforts to comply with the World Wide Web Consortium’s Web Content Accessibility Guidelines (WCAG) 2.1, Level AA — an internationally recognised standard for making web content more accessible to people with a wide range of disabilities.',
            'These guidelines offer recommendations for enhancing the accessibility of content for users with visual, auditory, cognitive, and motor impairments. We are continually working to improve the user experience for everyone and to apply relevant accessibility standards across our digital platforms.',
            'If you encounter a barrier on this site, please contact us at tmt@chemietradebd.net or call 02-223352155 and we will help you directly.',
        ],
    },
    'daily-update': {
        'title': 'Daily Update',
        'paragraphs': [
            'Daily Update. Project notes, tender deadlines and product availability from Techno Mate Technologies, published as new information reaches our desk.',
            '5 November 2026 — Tender support: our team is assisting industrial clients with documentation and deferred-payment guidance for eligible government tenders.',
            'This page is maintained by our project desk. For a time-sensitive enquiry, call 02-223352155 or email tmt@chemietradebd.net.',
        ],
    },
    'careers': {
        'title': 'Careers at Techno Mate Technologies',
        'paragraphs': [
            'Careers at Techno Mate Technologies. We supply and support industrial equipment across plant and machinery, energy and power, automation, steel and metal, and pharma and biotech. Our engineers, project managers and support staff work on live production sites, solving practical problems for manufacturers across Bangladesh.',
            'We look for people who are technically curious, comfortable on a plant floor, and serious about following a job through to the end. Experience with process equipment, rotating machinery, power systems, metal processing or industrial automation is valued, but the right attitude and a willingness to learn matter just as much.',
            'Current areas of interest include field service engineering, project engineering, application support, spare-parts coordination and technical sales. Roles are based from our Dhaka and Chattogram offices and involve regular customer site visits.',
            'To apply, send your CV and a short note about the role you are interested in to tmt@chemietradebd.net with “Careers” in the subject line. We review every application and will contact you if there is a fit.',
        ],
    },
    'cookie-policy': {
        'title': 'Cookie Policy',
        'paragraphs': [
            'Cookie Policy. This site uses cookies — small text files placed on your device — to help the site work reliably and to understand how it is used.',
            'Essential cookies keep you signed in to the tutorial library and protect forms against cross-site request forgery. Without them, account and form features cannot work.',
            'Analytics cookies, where enabled, help us understand which pages and tutorials are useful so we can improve them. They do not identify you personally in our reports.',
            'You can block or delete cookies in your browser settings. Blocking essential cookies may prevent you from signing in or using the contact and newsletter forms. For questions about this policy, contact tmt@chemietradebd.net.',
        ],
    },
    'e-tender-school': {
        'title': 'E-Tender School',
        'paragraphs': [
            'E-Tender School. A practical introduction to public and private electronic tenders for industrial equipment, works and services.',
            'The school covers tender search, eligibility, document preparation, technical compliance, pricing schedules and submission. Sessions are built around live examples from the sectors we serve: industrial plant and machinery, energy and power, automation, steel and metal, and pharma and biotech.',
            'We also help suppliers and buyers understand e-GP requirements, evaluation criteria and post-award contract management. To request a session or ask about a current tender, contact our team.',
        ],
    },
    'legal-notices': {
        'title': 'Legal Notices',
        'paragraphs': [
            'Legal Notices. This website is operated by Techno Mate Technologies, 10/G, Azad Center, 55-Purana Paltan, Dhaka-1000, Bangladesh.',
            'The content on this site is provided for general information about our products and services. Product descriptions, capacities and configurations are indicative; the specification agreed in a quotation or contract governs any supply.',
            'All text, images, logos and downloadable material on this site are owned by Techno Mate Technologies or used with permission, and may not be reproduced for commercial use without written consent.',
            'We take care to keep the information current, but we do not warrant that every page is complete or error-free. Links to third-party sites are provided for convenience and do not imply responsibility for their content.',
        ],
    },
    'privacy-policy': {
        'title': 'Privacy Policy',
        'paragraphs': [
            'Privacy Policy. Techno Mate Technologies collects only the information needed to respond to enquiries and operate the tutorial library.',
            'When you submit a contact or newsletter form, we receive the name, email address, company details and message you provide. When you create an account, we store your username, email address and a securely hashed password. Tutorial progress is stored against your account so you can resume where you left off.',
            'We use this information to answer your enquiry, provide access to tutorials, send the newsletter you asked for, and maintain the security of the site. We do not sell personal data.',
            'We keep enquiry records only as long as needed to handle the request and any resulting business relationship. Account data is kept while the account is active. You may ask us to correct or delete your data by writing to tmt@chemietradebd.net.',
            'The site uses cookies for sign-in, form security and basic usage measurement. See the Cookie Policy for details. Requests about access, correction or deletion are handled under applicable Bangladesh data-protection law.',
        ],
    },
    'terms-conditions': {
        'title': 'Terms & Conditions',
        'paragraphs': [
            'Terms & Conditions. By using this website you agree to these terms. If you do not agree, please do not use the site.',
            'The site is provided for information about Techno Mate Technologies and its products. You may view and print pages for your own business use, but you may not republish, scrape or resell the content without written permission.',
            'Quotations, specifications, delivery schedules and warranties are agreed separately in writing. Nothing on this website is an offer capable of acceptance, and product availability may change without notice.',
            'To the extent permitted by law, Techno Mate Technologies is not liable for indirect or consequential loss arising from use of this website. Nothing in these terms limits liability that cannot lawfully be limited.',
            'These terms are governed by the laws of Bangladesh. Any dispute is subject to the jurisdiction of the courts of Dhaka.',
        ],
    },
}
