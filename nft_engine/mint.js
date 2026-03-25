import {
  Connection,
  Keypair,
  clusterApiUrl
} from "@solana/web3.js";

import {
  Metaplex,
  keypairIdentity
} from "@metaplex-foundation/js";

import fs from "fs";

const secret = JSON.parse(
  fs.readFileSync(process.env.HOME + "/.config/solana/id.json")
);

const keypair = Keypair.fromSecretKey(new Uint8Array(secret));

const connection = new Connection(clusterApiUrl("devnet"));

const metaplex = Metaplex.make(connection)
  .use(keypairIdentity(keypair));

async function main() {
  console.log("🚀 Minting NFT...");

  const { nft } = await metaplex.nfts().create({
    uri: "https://arweave.net/123", // temp
    name: "SolClub NFT",
    sellerFeeBasisPoints: 0,
  });

  console.log("✅ NFT Minted!");
  console.log("Mint Address:", nft.address.toBase58());
}

main();