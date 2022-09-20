# AD Integration to WorkGraph
Code to populate and update ad users into workgraph.
The code pushes the data in a fixed json format to the queue given.


#### APIs exposed:
* /api/ad_integration/

#### API DOCS
API swagger docs can be found at the url `/static/docs.html`

#### Entities added in Graph:
* ADProfile
* Person
* ADInstance
* Company


#### Relationships added in Graph:
* has_profile (Person->ADProfile)
* belongs_to (Person->Company)

#### ON-BOARDING

##### Parameters Required:
ad_url, ad_username, ad_password, ad_search_base, graph_url, queue_url, state (used to confirm integration), group_id (company id)
##### Process:
* Using LDAP credentials fetch (updated) ADProfile data
* Check with previous ADProfile data for fields updated and update their lastUpdateTime
* ADProfile, Person, Company nodes data are sent to the queue 
* (Person->ADProfile) `has_profile` and (Person->Company) `belongs_to` relation data sent to the queue. 
* Set lastUpdateTime on the ADInstance node (for update)

#### UPDATE

##### Parameters Required and Process:
Same as on-board

## Getting Started

#### Django Server Environment Setup

* The Dockerfile sets up the environment for the django apache server and the sever comes up on port 8002.

#### Configurations
* Configurations can be found at `webserver/utils/constants.py`


## Running the tests
To tests for the code are written in webserver/tests package. To run all the automated tests :
```
python manage.py test webserver.tests
```