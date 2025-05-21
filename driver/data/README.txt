The 'serial-1' directory contains AS relationships inferred using the method
described in "AS Relationships, Customer Cones, and Validation"
published in IMC 2013 (https://catalog.caida.org/paper/2013_asrank).

The original perl script (https://publicdata.caida.org/datasets/2013-asrank-data-supplement/extra/asrank.pl) that performs AS relationships inference from BGP data has evolved over the years as follows:

- the data supplement release had the hard-coded range of assigned ASes. We updated the script to take the range of AS
  assignments published by IANA each month (starting March 2015.)

- beginning 2016, we forced the clique to a set of ASNs.  The first
  time we did this was for March 2016.  We passed
  --clique "174 209 286 701 1239 1299 2828 2914 3257 3320 3356 5511 6453 6461 6762 7018 12956" to the script.  This change was dictated by the fact that the inference method was not
  inferring a sensible clique, therefore we decided to override the clique inference to make publicly-available data useful.


- beginning July 2017, we used a different automated method to infer
  the clique.  We ran this code off-and-on until August 2019 depending
  on the clique that the code inferred.  We then switched back to a
  static clique in August 2019.

- beginning December 2022, we report the AS relationships tagged with
  the step of the algorithm that inferred the relationship, using
  step comments before each block of relationship inferences in that step.
  The steps are:

# step 1: set peering in clique
# step 2: initial provider assignment
# step 3: providers for stub ASes #1
# step 4: provider to larger customer
# step 5: provider-less networks
# step 6: c2p for stub-clique relationships
# step 7: fold p2p links
# step 8: everything else is p2p

Note that we did not go back and re-infer prior datasets as the script
changed.

The as-rel files contain p2p and p2c relationships.  The format is:
<provider-as>|<customer-as>|-1
<peer-as>|<peer-as>|0

The ppdc-ases files contain the provider-peer customer cones inferred for
each AS.  Each line specifies an AS and all ASes we infer to be reachable
following a customer link.  The format is:
<cone-as> <customer-1-as> <customer-2-as> .. <customer-N-as>

The all-paths files contain route announcements in the BGP RIB files we processed to infer the relationships for the given snapshot.
Each line has the following format:
<organization running the collector>/<name of BGPstream collector>|<frequency of observations for a path> <as path> <prefix> <bgp-origin-attribute> <peer ip address>

We disabled public access to 2020-02 and 2020-03 data since some of the links were not calculated correctly, therefore producing errors in customer cone and ranks

------------------------
Acceptable Use Agreement
------------------------

https://www.caida.org/about/legal/aua/public_aua/

When referencing this data (as required by the AUA), please use:

The CAIDA AS Relationships Dataset, <date range used>
    https://www.caida.org/catalog/datasets/as-relationships/

Also, please, report your publication to CAIDA
(https://www.caida.org/catalog/datasets/publications/report-publication).