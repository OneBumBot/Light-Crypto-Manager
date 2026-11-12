package main
import("encoding/binary";"testing")
func TestMalformedFramesNeverReturnData(t *testing.T){
 for _,size:=range []int{0,1,8,64,65,66,65+1024+4113}{
  raw:=make([]byte,size);if len(raw)>=8{copy(raw,[]byte("LCMKUZ01"))}
  got:=invoke(raw);if len(got)!=1 || got[0]==0{t.Fatalf("malformed frame emitted data: size %d",size)}
 }
 raw:=make([]byte,65);copy(raw,[]byte("LCMKUZ01"));raw[8]=1
 binary.BigEndian.PutUint32(raw[57:61],0xffffffff)
 if got:=invoke(raw);len(got)!=1 || got[0]!=2{t.Fatal("unbounded length accepted")}
}
