cd jext
gradle jar
mkdir -p extlibs
cd extlibs
mvn dependency:get -Ddest=./guava-19.0.jar -DgroupId=com.google.guava -DartifactId=guava -Dversion=19.0 -Dpackaging=jar
mvn dependency:get -Ddest=./javax.servlet-api-3.1.0.jar -DgroupId=javax.servlet -DartifactId=javax.servlet-api -Dversion=3.1.0 -Dpackaging=jar
