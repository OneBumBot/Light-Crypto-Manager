// Local one-shot binary protocol, no network, argv keys, FFI or shared cipher instance.
package main

import (
 "bytes"
 "encoding/binary"
 "io"
 "os"
 "github.com/tarantool/go-gostcrypto/kuznyechik"
 "github.com/tarantool/go-gostcrypto/mgm"
)

// Input: magic8 | op1 | key32 | ICN16 | AADlen32BE | datalen32BE | AAD | data.
// Output: status byte (0 success, 1 authentication failure, 2 malformed, 3 internal) | data on success only.
func invoke(raw []byte) (out []byte) {
 defer func(){ if recover()!=nil { out=[]byte{3} } }()
 if len(raw)<65 || len(raw)>65+1024+4112 || !bytes.Equal(raw[:8],[]byte("LCMKUZ01")){ return []byte{2} }
 op:=raw[8];key:=raw[9:41];nonce:=raw[41:57];a32:=binary.BigEndian.Uint32(raw[57:61]);n32:=binary.BigEndian.Uint32(raw[61:65])
 if a32>1024 || n32>4112{return []byte{2}}
 a:=int(a32);n:=int(n32)
 if a>1024 || n>4112 || len(raw)!=65+a+n { return []byte{2} }
 ad:=raw[65:65+a];data:=raw[65+a:]
 block:=kuznyechik.NewCipherCT(key)
 if op==3 || op==4 {
  if n!=16 || a!=0{return []byte{2}}
  result:=make([]byte,16)
  if op==3{block.Encrypt(result,data)}else{block.Decrypt(result,data)}
  return append([]byte{0},result...)
 }
 if nonce[0]&0x80!=0{return []byte{2}}
 mode,err:=mgm.NewMGM(block,16);if err!=nil{return []byte{3}}
 switch op {
 case 1:
  if n>4096 || a+n==0{return []byte{2}}
  return append([]byte{0},mode.Seal(nil,nonce,data,ad)...)
 case 2:
  if n<16 || a+n-16==0{return []byte{2}}
  plain,err:=mode.Open(nil,nonce,data,ad)
  if err!=nil{return []byte{1}} // No plaintext has been emitted or appended to caller storage.
  return append([]byte{0},plain...)
 default:return []byte{2}
 }
}
func main(){ raw,err:=io.ReadAll(io.LimitReader(os.Stdin,65+1024+4112+1));if err!=nil{os.Stdout.Write([]byte{2});return};out:=invoke(raw);os.Stdout.Write(out) }
