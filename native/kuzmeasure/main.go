// Offline instrumentation binary, NOT copied into runtime images or live dispatch.
package main
import("crypto/rand";"encoding/binary";"encoding/json";"io";"os";"time";"github.com/tarantool/go-gostcrypto/kuznyechik";"github.com/tarantool/go-gostcrypto/mgm")
func main(){
 if len(os.Args)>1 && os.Args[1]=="ping"{os.Stdout.Write([]byte{0});return}
 if len(os.Args)>1 && os.Args[1]=="echo"{
  for i:=0;i<1000;i++ {h:=make([]byte,4);if _,e:=io.ReadFull(os.Stdin,h);e!=nil{return};n:=binary.BigEndian.Uint32(h);if n>2048{return};b:=make([]byte,int(n));if _,e:=io.ReadFull(os.Stdin,b);e!=nil{return};os.Stdout.Write(h);os.Stdout.Write(b)};return
 }
 key:=make([]byte,32);rand.Read(key);block:=kuznyechik.NewCipherCT(key);mode,_:=mgm.NewMGM(block,16)
 aad:=make([]byte,128);plain:=make([]byte,83);nonce:=make([]byte,16)
 setup:=[]int64{};enc:=[]int64{};dec:=[]int64{};fixed:=[]int64{};random:=[]int64{}
 for i:=uint64(1);i<=1000;i++{
  k:=make([]byte,32);rand.Read(k);t:=time.Now();kuznyechik.NewCipherCT(k);setup=append(setup,time.Since(t).Nanoseconds())
  binary.BigEndian.PutUint64(nonce[8:],i);t=time.Now();ct:=mode.Seal(nil,nonce,plain,aad);enc=append(enc,time.Since(t).Nanoseconds());t=time.Now();p,e:=mode.Open(nil,nonce,ct,aad);dec=append(dec,time.Since(t).Nanoseconds());if e!=nil || len(p)!=83{panic("verification")}
 }
 for i:=uint64(1001);i<=6000;i++{
  k:=make([]byte,32);rand.Read(k);other,_:=mgm.NewMGM(kuznyechik.NewCipherCT(k),16);binary.BigEndian.PutUint64(nonce[8:],i)
  // Alternate order to reduce drift; random generation and setup outside timed call.
  if i%2==0{t:=time.Now();mode.Seal(nil,nonce,plain,aad);fixed=append(fixed,time.Since(t).Nanoseconds());t=time.Now();other.Seal(nil,nonce,plain,aad);random=append(random,time.Since(t).Nanoseconds())
  }else{t:=time.Now();other.Seal(nil,nonce,plain,aad);random=append(random,time.Since(t).Nanoseconds());t=time.Now();mode.Seal(nil,nonce,plain,aad);fixed=append(fixed,time.Since(t).Nanoseconds())}
 }
 json.NewEncoder(os.Stdout).Encode(map[string]any{"key_setup_ns":setup,"native_encrypt_ns":enc,"native_decrypt_ns":dec,"fixed_class_ns":fixed,"random_class_ns":random})
}
