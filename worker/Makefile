# Compilación del robot. Opciones de endurecimiento: protector de pila, FORTIFY_SOURCE,
# ejecutable independiente de la posición (PIE) y relocalizaciones de solo lectura (RELRO).
CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Wpedantic -fstack-protector-strong -fPIE -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=2
LDFLAGS  ?= -pie -Wl,-z,relro,-z,now
LDLIBS   := -lcurl

FUENTES := $(wildcard src/*.cpp)
OBJETOS := $(FUENTES:.cpp=.o)

robot: $(OBJETOS)
	$(CXX) $(OBJETOS) -o $@ $(LDFLAGS) $(LDLIBS)

src/%.o: src/%.cpp $(wildcard src/*.hpp)
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f robot src/*.o

.PHONY: clean
