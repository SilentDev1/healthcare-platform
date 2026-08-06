# Search privacy

Healthcare searches can reveal sensitive intent even without names. Persistent logs therefore
exclude raw query text, IP addresses, cookies, member identifiers, and user profiles. Structured
events retain only correlation ID, route, query length, result count, and timing. Access logs
must follow the same policy. The platform contains no PHI and search is never used to infer a
diagnosis or recommend treatment.
