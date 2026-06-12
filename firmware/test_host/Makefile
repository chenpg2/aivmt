# Host build of the SpSession FSM test (no ESP-IDF). Used as a /goal verification target.
CXX ?= c++
CXXFLAGS := -std=c++17 -Wall -I../components/aivmt_sp/include -Istubs

COMPONENT := ../components/aivmt_sp
SRCS := test_fsm.cc \
	$(COMPONENT)/sp_session.cc \
	$(COMPONENT)/sp_telemetry.cc \
	$(COMPONENT)/sp_persona.cc \
	$(COMPONENT)/sp_ptt.cc \
	$(COMPONENT)/sp_participant.cc

fsm_test: $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $(SRCS)

.PHONY: test clean
test: fsm_test
	./fsm_test

clean:
	rm -f fsm_test
