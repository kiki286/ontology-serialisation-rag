# Gold Questions and Answers

##  Q1

### Question
What are the key concepts in IDO?

### Answer
IDO has five top-level concepts (each with taxonomic breakdowns). The five top-level concepts are Dependent, Object, Specified, Actual, Temporal

### Source
There could also be several sources for this information, but one source is the diagram here https://rds.posccaesar.org/ontology/lis14/

### Comment
There could be several ways to answer this question, but I would really like it to see the “key concepts” here and summarise the ontology with its top-level entities.

## Q2

### Question
What is IDO and why would I use it?

### Answer
The Industrial Data Ontology (IDO) is a W3C OWL 2 ontology. The IDO is intended for use in all life cycle phases of industrial assets and processes, to build vocabularies and manage asset models that employ Reference Data Libraries (RDLs).

### Source
https://rds.posccaesar.org/ontology/lis14/

### Comment
Again, there could be several ways for it to answer this question. But really I want to know that it’s an OWL2 ontology and it’s about industrial assets.

## Q3

### Question
I want to model Failure Modes. Where does a “Failure Effect” sit in IDO?

### Answer
If a failure effect is defined as, “The consequence of a ‘FailureMode’ in terms of the operation, function or status of the item (IEC 60812:2008).”, a failure effect would sit under the “Activity” concept in IDO. This is an opinion based on the definition provided, and should be discussed with domain experts.

### Source
IEC 60812:2008

### Comment
It might need to ask some more questions about what a failure mode is and how it’s defined before the assistant can correctly place it in IDO. Let’s see if this sort of question works, it could be out of scope. The sources here are the definitions of the terms. It would also be good to caveat this kind of question with “the best person to ask is a domain” expert.

## Q4

### Question
Explain an Activity Profile to me and give me an example of how I would use it

### Answer
An activity profile is “An activity obtained by "selective abstraction" to just that part of an activity that consists in varying or maintaining a specified 'quality' of a participant”. An example is “An 'activity profile' of an 'activity' involving rotating equipment, instantiating a class "100 revolutions per minute".

### Source
https://rds.posccaesar.org/ontology/lis14/rdl/ActivityProfile/

### Comment
It would be interesting if it could then be re-prompted after giving its answer and give a different example that is still correct. It would also be interesting to see if it can give the true definition from the source and then a layman’s description from the source.

## Q5

### Question
I have a Failure Mode Code (representing the failure mode that has occurred) and I have modelled that as an information object. I also want to model the actual Failure Mode that occurred on the equipment. What IDO relation do I use between the Failure Mode Code and the Failure Mode.

### Answer
If a failure mode code is an information object, and a failure mode is an Activity then to correct object property to use in this case would be “is about” (domain: information object, range: anything).  

### Source
https://rds.posccaesar.org/ontology/lis14/rdl/isAbout/

### Comment
Can it select the best object property based on their definitions?

## Q6

### Question
What is the difference between a Location and a Site in IDO?

### Answer
A location is defined as “An object that is a region in space” (example: An outdoor plant area, an opening in a wall, the space inside an enclosure) and a site is defined as “A location determined in relation to one or more physical objects.” (example: A flight deck, the inside of a manifold, the hold of a ship, a centre of gravity, an outside area)

### Source
https://rds.posccaesar.org/ontology/lis14/rdl/Location/, https://rds.posccaesar.org/ontology/lis14/rdl/Site/

### Comment
It would also be interesting to see the real definitions, and the how it helps the user to understand those definitions.

## Q7

### Question
What OWL profile does IDO use?

### Answer
IDO uses OWL2 DL. 

### Source
https://rds.posccaesar.org/WD_IDO.pdf (pg 9)

### Comment
It would be interesting to see if it picks up the “DL” part and if it can further explain the reasoning profile on prompting. This is an example where we grab a fact from the source, and then we can explain what that means using the raw GPT.

## Q8

### Question
I want to create a reference ontology for failure modes aligned with IDO, what should my namespace for my ontology look like?

### Answer
Reference ontologies should have a namespace of the structure http://rds.posccaesar.org/ontology/XXX/ont/core where X is the name of the reference ontology. So this example may be of the form http://rds.posccaesar.org/ontology/failure-modes/ont/core

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ section 8.3.

### Comment

## Q9

### Question
If I create a concept in an IDO aligned ontology, what annotations / metadata is required on that concept.

### Answer
The principles document state two annotations that are required. That is rdfs:label and skos:defintions. Additional annotation properties are supported by IDO but are only recommended for use.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ (Section 9.2)

### Comment
I wonder if it can distinguish between the required and recommended properties.

## Q10

### Question
When was IDO last updated?

### Answer
The IDO ontology was last updated on the 28th of November 2024.

### Source
https://rds.posccaesar.org/ontology/lis14/ont/core/

### Comment
I wonder what artefacts it will consider the version of in its answer (i.e. ontology vs documentation)

## Q11

### Question
What is the difference between OBI and IDO?

### Answer
OBI stands for Ontology-based interoperability for industrial data. It is the name of a new ISO standard series ISO 23726. The OBI ecosystem includes ontologies, artefacts, stakeholders, and processes. In order to be part of the OBI ecosystem, ontology models have to adhere to the ontological commitments of IDO. The Industrial Data Ontology (IDO) is the upper ontology in the ISO 23726 series. IDO is being published as ISO DIS 23726-3. 

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ 

### Comment

## Q12

### Question
What are the principles of OBI

### Answer
The OBI document proposes a set of principles which ontology resources will have to comply with in order to be considered compliant with IDO and the ISO 23726 series. There are 10 principles listed in Section 6 of the document. They are listed as follows:
-	Direct Semantics consistent
-	Resource description framework (RDF and RDFS)
-	Digital resource
-	Axioms, rules and constraints
-	Ontology alignment, review and documentation
-	Annotation
-	Versioning and storage of artefacts
-	Ontology modularisation
-	Ontology evaluation
-	Ontology maintenance agencies and process

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ 

### Comment

## Q13

### Question
What is an ontology maintenance agency?

### Answer
OBI artefacts issued by the ISO OBI standards (ISO 23726) community shall be managed by a maintenance agency. A maintenance agency is responsible for maintaining the publishing updates to digital versions of artefacts that are part of the ISO 23726 series. 
A maintenance agency must be able to assess ontology artefacts to assure that they meet the requirements set out in Section 6 of the OBI document.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ 

### Comment

## Q14

### Question
What does a maintenance agency do?

### Answer
A maintenance agency has the following characteristics
1.	A maintenance agency is responsible for maintaining and publishing updates to digital versions of artefacts that are part of the ISO 23726 series.
2.	A maintenance agency shall have a documented maintenance process.
3.	A maintenance agency provides an independent evaluation of the alignment of digital artefacts to ensure conformance with the principles in Clause 6 of the ISO 23726-1 standard.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ 

### Comment

## Q15

### Question
What sort of ontology checks are required for ontology resources to be considered part of OBI?

### Answer
All ontologies in the OBI series shall have suitable ontology quality tests. These tests should provide evidence of ontology evaluation with, for example, model checking processes, syntax checkers, and reasoners. Processes for ontology evaluation of OBI artefacts managed by external groups are the responsibility of the external group and the evaluation should be done to a standard equivalent to that of the ISO 23726 maintenance agency.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ 

### Comment

## Q16

### Question
Who maintains ontologies aligned to IDO that are not part of ISO?

### Answer
External groups can own and manage IDO-aligned ontology resources. The involvement of external groups is a core part of the vision for an OBI ecosystem. Processes for ontology evaluation of OBI artefacts managed by external groups are the responsibility of the external group and the evaluation should be done to a standard equivalent to that of the ISO 23726 maintenance agency. 

### Source

### Comment

## Q17

### Question
Does IDO use Linked Data?

### Answer
Yes, ontologies, ontology modules and ontology patterns in the OBI series shall conform to the W3C Linked Data standard and protocols.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ - Clause 6.2

### Comment

## Q18

### Question
What is a shortcut property

### Answer
A shortcut property is an OWL object or datatype property intended as equivalent in meaning to a modelling pattern that would involve additional entities or classifications if made fully explicit. The meaning of a shortcut property can in general be partially captured by OWL property chains. Shortcut properties are used in the OBI series to support modelling at different levels of detail. 

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/ - Clause 5.8.4

### Comment

## Q19

### Question
What are the differences between an upper ontology, reference ontology, application ontology, and enterprise ontology?

### Answer
An upper ontology is an ontology of abstract concepts and general relationships that are common across all domains. A reference ontology is an ontology based on a shared understanding of the concepts and relationships within a specific domain or field of knowledge. A reference ontology models key concepts in a domain so that other more specialized ontologies or applications can reuse or extend it. A trusted reference ontology (3.1.3) can be used across multiple applications. An application ontology is ontology developed for a particular task or use case that contains only the concepts, relationships, and constraints necessary for the context. An enterprise ontology is an ontology developed, owned, and maintained by an enterprise. Enterprise ontologies include reference ontologies and application ontologies.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/

### Comment
There is no agreement in the community as to a naming convention for ontologies. Various names such as Core, Domain, Domain-independent, Domain-dependent are used to describe ontologies but these terms are not agreed or clearly defined. 

## Q20

### Question
What are annotation properties?

### Answer
Annotation properties in ontologies are a vital part of documentation to ensure a shared understanding of the resource and how it should be used. The OBI principles document requires the use of two annotation properties rdfs:label and skos:definitions and suggests the use of many more. Annotation properties are not used by the OWL reasoner.

### Source
https://pca-posc-caesar-association.github.io/Public_ISO23726-1/latest/

### Comment

## Q21

### Question
Is IDO available in different languages?

### Answer
Yes, versions of the IDO ontology file (as a .ttl) have been produced in Norwegian, German, Korean and Japanese using AI translation of the source text file managed in an EMACS package called ELOT https://github.com/johanwk/elot .

### Source

### Comment
I (melinda) have some slides showing this.

## Q22

### Question
Does the class InformationObject in IDO include documents and database records?

### Answer
Yes, but they must be given some physical form to exist, for documents this may be a paper printout and for the database record this could be a configuration of electrons in computer memory. This physical representation of an information object is called a 'concretization'. IDO uses the concretizedBy relation.

### Source
IDO doc appendix A3

### Comment

## Q23

### Question
In IDO what is the difference between the classes 'function', 'capability' and 'disposition?

### Answer

Each managed item in an industrial plant is there to serve a function (a purpose). Every function is a capability, and every capability is a disposition. This class hierarchy allows for a suitable degree of distinction between types of behaviour,
from the overall level of plant systems down to individual pieces of equipment.

Function a capability that is the reason for the object’s existence or presence
Capability a favourable disposition that is not a primary purpose
Disposition what an object tends to do

### Source
IDO doc appendix A4

### Comment

## Q24

### Question
In IDO what is meant by a Dependent class?

### Answer
A Dependent class is a class that only exists given that a independent object that bears the specified dependency exists. Examples of subclasses of the Dependent class include Disposition, Function, Role, and Quality.  

### Source
IDO doc appendix A1

### Comment

## Q25

### Question
What are the different Object classes?

### Answer

### Source

### Comment



